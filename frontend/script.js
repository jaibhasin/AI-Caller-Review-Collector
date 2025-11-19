class VoiceReviewCollector {
    constructor() {
        this.ws = null;
        this.mediaRecorder = null;
        this.audioStream = null;
        this.isRecording = false;
        this.isConnected = false;
        this.callStartTime = null;
        this.callDurationInterval = null;
        this.audioChunks = [];
        
        // Global AudioContext - will be created on user interaction for macOS compatibility
        this.audioContext = null;
        this.audioQueue = Promise.resolve();
        
        // Audio buffering for streaming chunks
        this.currentAudioChunks = [];
        this.isReceivingAudio = false;
        this.audioTimeoutId = null;
        
        // Statistics
        this.stats = {
            totalCalls: 0,
            reviewsCollected: 0,
            totalCallDuration: 0
        };
        
        this.initializeElements();
        this.attachEventListeners();
        this.loadStats();
    }
    
    initializeElements() {
        // Buttons
        this.startCallBtn = document.getElementById('startCallBtn');
        this.recordBtn = document.getElementById('recordBtn');
        this.endCallBtn = document.getElementById('endCallBtn');
        this.clearBtn = document.getElementById('clearConversation');
        
        // Status elements
        this.connectionStatus = document.getElementById('connectionStatus');
        this.callDuration = document.getElementById('callDuration');
        this.conversationContent = document.getElementById('conversationContent');
        this.audioVisualizer = document.getElementById('audioVisualizer');
        
        // Stats elements
        this.totalCallsEl = document.getElementById('totalCalls');
        this.reviewsCollectedEl = document.getElementById('reviewsCollected');
        this.avgDurationEl = document.getElementById('avgDuration');
        
        // Toast
        this.toast = document.getElementById('toast');
        this.toastMessage = document.getElementById('toastMessage');
    }
    
    attachEventListeners() {
        this.startCallBtn.addEventListener('click', () => this.startCall());
        this.endCallBtn.addEventListener('click', () => this.endCall());
        this.clearBtn.addEventListener('click', () => this.clearConversation());
        
        // Record button - hold to talk
        this.recordBtn.addEventListener('mousedown', () => this.startRecording());
        this.recordBtn.addEventListener('mouseup', () => this.stopRecording());
        this.recordBtn.addEventListener('mouseleave', () => this.stopRecording());
        
        // Touch events for mobile
        this.recordBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.startRecording();
        });
        this.recordBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            this.stopRecording();
        });
    }
    
    async startCall() {
        try {
            this.showToast('Connecting to AI agent...', 'info');
            
            // CRITICAL for macOS: Create/Resume AudioContext synchronously during user gesture
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
                console.log('AudioContext created, state:', this.audioContext.state);
            }
            
            // Resume must be called synchronously within user gesture handler on macOS
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
                console.log('AudioContext resumed, state:', this.audioContext.state);
            }
            
            // Request microphone permission
            this.audioStream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });
            
            // Connect to WebSocket
            this.ws = new WebSocket('ws://localhost:8000/api/agent/voice');
            
            this.ws.onopen = () => {
                this.isConnected = true;
                this.updateConnectionStatus(true);
                this.startCallBtn.disabled = true;
                this.recordBtn.disabled = false;
                this.endCallBtn.disabled = false;
                this.callStartTime = Date.now();
                this.startCallDurationTimer();
                this.showToast('Connected! AI agent is ready to collect feedback.', 'success');
                this.stats.totalCalls++;
                this.updateStats();
            };
            
            this.ws.onmessage = (event) => {
                if (typeof event.data === 'string') {
                    // Text message with conversation data
                    const data = JSON.parse(event.data);
                    this.handleConversationMessage(data);
                } else {
                    // Binary audio data - buffer streaming chunks
                    this.handleAudioChunk(event.data);
                }
            };
            
            this.ws.onclose = () => {
                this.handleDisconnection();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.showToast('Connection error. Please try again.', 'error');
                this.handleDisconnection();
            };
            
        } catch (error) {
            console.error('Error starting call:', error);
            this.showToast('Microphone access denied. Please allow microphone access.', 'error');
        }
    }
    
    endCall() {
        if (this.ws) {
            this.ws.close();
        }
        this.handleDisconnection();
        this.showToast('Call ended. Thank you for collecting feedback!', 'info');
    }
    
    handleDisconnection() {
        this.isConnected = false;
        this.updateConnectionStatus(false);
        this.startCallBtn.disabled = false;
        this.recordBtn.disabled = true;
        this.endCallBtn.disabled = true;
        this.stopCallDurationTimer();
        this.stopAudioVisualizer();
        
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
            this.audioStream = null;
        }
        
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
    }
    
    async startRecording() {
        if (!this.isConnected || this.isRecording) return;
        
        try {
            this.isRecording = true;
            this.recordBtn.classList.add('recording');
            this.recordBtn.innerHTML = '<i class="fas fa-stop"></i><span>Recording...</span>';
            this.startAudioVisualizer();
            
            this.audioChunks = [];
            // Use WebM format (most widely supported by browsers)
            // We'll handle the conversion on the server side
            let mimeType = 'audio/webm;codecs=opus';
            
            // Check what the browser actually supports
            if (!MediaRecorder.isTypeSupported(mimeType)) {
                // Fallback options
                if (MediaRecorder.isTypeSupported('audio/webm')) {
                    mimeType = 'audio/webm';
                } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    mimeType = 'audio/mp4';
                } else {
                    console.warn('No supported audio format found, using default');
                    mimeType = '';
                }
            }
            
            console.log('Using audio format:', mimeType);
            this.mediaRecorder = new MediaRecorder(this.audioStream, {
                mimeType: mimeType
            });
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = async () => {
                // When recording stops, send the audio to server
                const audioBlob = new Blob(this.audioChunks, { type: mimeType });
                this.sendAudioToServer(audioBlob);
            };

            
            this.mediaRecorder.start();
            
        } catch (error) {
            console.error('Error starting recording:', error);
            this.showToast('Recording error. Please try again.', 'error');
            this.isRecording = false;
        }
    }
    
    stopRecording() {
        if (!this.isRecording) return;
        
        this.isRecording = false;
        this.recordBtn.classList.remove('recording');
        this.recordBtn.innerHTML = '<i class="fas fa-microphone"></i><span>Hold to Talk</span>';
        this.stopAudioVisualizer();
        
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
    }
    
    async sendAudioToServer(audioBlob) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        
        try {
            // Convert to ArrayBuffer and send
            const arrayBuffer = await audioBlob.arrayBuffer();
            this.ws.send(arrayBuffer);
            
        } catch (error) {
            console.error('Error sending audio:', error);
            this.showToast('Failed to send audio. Please try again.', 'error');
        }
    }
    
    handleConversationMessage(data) {
        if (data.user_text) {
            this.addMessageToConversation('user', data.user_text);
        }
        
        if (data.agent_reply) {
            this.addMessageToConversation('agent', data.agent_reply);
            this.stats.reviewsCollected++;
            this.updateStats();
        }
        
        if (data.error) {
            this.showToast(`Error: ${data.error}`, 'error');
        }
    }
    
    addMessageToConversation(type, text) {
        // Remove placeholder if it exists
        const placeholder = this.conversationContent.querySelector('.message-placeholder');
        if (placeholder) {
            placeholder.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        const headerDiv = document.createElement('div');
        headerDiv.className = 'message-header';
        headerDiv.textContent = type === 'user' ? 'You' : 'AI Agent';
        
        const contentDiv = document.createElement('div');
        contentDiv.textContent = text;
        
        messageDiv.appendChild(headerDiv);
        messageDiv.appendChild(contentDiv);
        
        this.conversationContent.appendChild(messageDiv);
        this.conversationContent.scrollTop = this.conversationContent.scrollHeight;
    }
    
    handleAudioChunk(audioData) {
        // Simple approach: collect chunks and play when done
        if (!this.isReceivingAudio) {
            this.isReceivingAudio = true;
            this.currentAudioChunks = [];
            console.log('Started receiving audio');
        }
        
        // Add this chunk to our collection
        this.currentAudioChunks.push(audioData);
        console.log(`Got audio chunk ${this.currentAudioChunks.length}`);
        
        // Wait a bit for more chunks, then play everything
        clearTimeout(this.audioTimeoutId);
        this.audioTimeoutId = setTimeout(() => {
            this.playAllAudioChunks();
        }, 150); // Wait 150ms for more chunks
    }
    
    async playAllAudioChunks() {
        if (this.currentAudioChunks.length === 0) {
            this.isReceivingAudio = false;
            return;
        }
        
        console.log(`Playing ${this.currentAudioChunks.length} audio chunks`);
        
        // Combine all chunks into one audio file
        const completeAudio = new Blob(this.currentAudioChunks, { type: 'audio/mpeg' });
        
        // Reset for next audio
        this.currentAudioChunks = [];
        this.isReceivingAudio = false;
        
        // Play the complete audio
        await this.playAudioResponse(completeAudio);
    }
    
    async playAudioResponse(audioData) {
        // Simplified audio playback - just use HTML5 Audio (works better)
        this.audioQueue = this.audioQueue.then(async () => {
            try {
                // Convert audio data to a blob that browser can play
                const audioBlob = audioData instanceof Blob ? 
                    audioData : 
                    new Blob([audioData], { type: 'audio/mpeg' });
                
                if (audioBlob.size === 0) {
                    console.warn('Empty audio, skipping');
                    return;
                }
                
                // Create a temporary URL for the audio
                const audioUrl = URL.createObjectURL(audioBlob);
                const audio = new Audio(audioUrl);
                
                // Play the audio and wait for it to finish
                return new Promise((resolve) => {
                    audio.onended = () => {
                        URL.revokeObjectURL(audioUrl); // Clean up memory
                        console.log('Audio finished playing');
                        resolve();
                    };
                    audio.onerror = (e) => {
                        console.error('Audio playback error:', e);
                        URL.revokeObjectURL(audioUrl);
                        resolve();
                    };
                    audio.play().catch(e => {
                        console.error('Could not play audio:', e);
                        URL.revokeObjectURL(audioUrl);
                        resolve();
                    });
                });
                
            } catch (error) {
                console.error('Audio processing error:', error);
            }
        }).catch(error => {
            console.error('Audio queue error:', error);
        });
    }
    
    updateConnectionStatus(connected) {
        const statusIcon = this.connectionStatus.querySelector('i');
        const statusText = this.connectionStatus.querySelector('span');
        
        if (connected) {
            this.connectionStatus.classList.add('connected');
            this.connectionStatus.classList.remove('disconnected');
            statusText.textContent = 'Connected';
        } else {
            this.connectionStatus.classList.add('disconnected');
            this.connectionStatus.classList.remove('connected');
            statusText.textContent = 'Disconnected';
        }
    }
    
    startCallDurationTimer() {
        this.callDurationInterval = setInterval(() => {
            if (this.callStartTime) {
                const duration = Date.now() - this.callStartTime;
                const minutes = Math.floor(duration / 60000);
                const seconds = Math.floor((duration % 60000) / 1000);
                this.callDuration.querySelector('span').textContent = 
                    `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            }
        }, 1000);
    }
    
    stopCallDurationTimer() {
        if (this.callDurationInterval) {
            clearInterval(this.callDurationInterval);
            this.callDurationInterval = null;
        }
        
        if (this.callStartTime) {
            const callDuration = Date.now() - this.callStartTime;
            this.stats.totalCallDuration += callDuration;
            this.callStartTime = null;
            this.updateStats();
        }
        
        this.callDuration.querySelector('span').textContent = '00:00';
    }
    
    startAudioVisualizer() {
        this.audioVisualizer.classList.add('active');
    }
    
    stopAudioVisualizer() {
        this.audioVisualizer.classList.remove('active');
    }
    
    clearConversation() {
        this.conversationContent.innerHTML = `
            <div class="message-placeholder">
                <i class="fas fa-comment-dots"></i>
                <p>Start a call to begin collecting feedback</p>
            </div>
        `;
    }
    
    updateStats() {
        this.totalCallsEl.textContent = this.stats.totalCalls;
        this.reviewsCollectedEl.textContent = this.stats.reviewsCollected;
        
        if (this.stats.totalCalls > 0) {
            const avgDuration = this.stats.totalCallDuration / this.stats.totalCalls;
            const avgMinutes = Math.floor(avgDuration / 60000);
            const avgSeconds = Math.floor((avgDuration % 60000) / 1000);
            this.avgDurationEl.textContent = 
                `${avgMinutes}:${avgSeconds.toString().padStart(2, '0')}`;
        }
        
        this.saveStats();
    }
    
    saveStats() {
        localStorage.setItem('voiceReviewStats', JSON.stringify(this.stats));
    }
    
    loadStats() {
        const savedStats = localStorage.getItem('voiceReviewStats');
        if (savedStats) {
            this.stats = { ...this.stats, ...JSON.parse(savedStats) };
            this.updateStats();
        }
    }
    
    showToast(message, type = 'info') {
        this.toast.className = `toast ${type}`;
        this.toastMessage.textContent = message;
        this.toast.classList.add('show');
        
        setTimeout(() => {
            this.toast.classList.remove('show');
        }, 4000);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new VoiceReviewCollector();
});

// Handle browser compatibility
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    document.addEventListener('DOMContentLoaded', () => {
        const toast = document.getElementById('toast');
        const toastMessage = document.getElementById('toastMessage');
        toast.className = 'toast error show';
        toastMessage.textContent = 'Your browser does not support audio recording. Please use a modern browser.';
    });
}
