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
            this.mediaRecorder = new MediaRecorder(this.audioStream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
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
        // Start buffering audio chunks
        if (!this.isReceivingAudio) {
            this.isReceivingAudio = true;
            this.currentAudioChunks = [];
            console.log('Started receiving audio stream');
        }
        
        // Add chunk to buffer
        this.currentAudioChunks.push(audioData);
        console.log(`Buffering chunk ${this.currentAudioChunks.length}, size:`, audioData.byteLength || audioData.size);
        
        // Reset timeout - if no new chunks arrive within 100ms, play the buffered audio
        clearTimeout(this.audioTimeoutId);
        this.audioTimeoutId = setTimeout(() => {
            this.playBufferedAudio();
        }, 100);
    }
    
    async playBufferedAudio() {
        if (this.currentAudioChunks.length === 0) {
            this.isReceivingAudio = false;
            return;
        }
        
        console.log(`Playing ${this.currentAudioChunks.length} buffered chunks`);
        const chunksToPlay = [...this.currentAudioChunks];
        this.currentAudioChunks = [];
        this.isReceivingAudio = false;
        
        // Combine all chunks into single blob
        const completeAudioBlob = new Blob(chunksToPlay, { type: 'audio/mpeg' });
        console.log('Combined audio blob size:', completeAudioBlob.size, 'bytes');
        
        // Play using queue
        await this.playAudioResponse(completeAudioBlob);
    }
    
    async playAudioResponse(audioData) {
        // Use sequential queue-based playback to prevent overlap and ensure reliability
        this.audioQueue = this.audioQueue.then(async () => {
            try {
                if (!this.audioContext) {
                    console.error('AudioContext not initialized - user must click Start Call first');
                    return;
                }
                
                console.log('Playing audio, AudioContext state:', this.audioContext.state);
                
                // Convert to ArrayBuffer
                let arrayBuffer;
                if (audioData instanceof Blob) {
                    arrayBuffer = await audioData.arrayBuffer();
                } else if (audioData instanceof ArrayBuffer) {
                    arrayBuffer = audioData;
                } else {
                    arrayBuffer = await new Blob([audioData], { type: 'audio/mpeg' }).arrayBuffer();
                }
                
                if (arrayBuffer.byteLength === 0) {
                    console.warn('Empty audio buffer, skipping');
                    return;
                }
                
                console.log('Decoding', arrayBuffer.byteLength, 'bytes...');
                
                // Decode audio data using global AudioContext
                const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
                console.log('Decoded:', audioBuffer.duration.toFixed(2), 'seconds');
                
                // Create and configure buffer source
                const source = this.audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.audioContext.destination);
                
                // Play audio and wait for it to complete
                return new Promise((resolve) => {
                    source.onended = () => {
                        console.log('Playback completed');
                        resolve();
                    };
                    source.start();
                    console.log('Audio playing...');
                });
                
            } catch (error) {
                console.error('Error playing audio:', error.name, error.message);
                // Fallback to HTML5 Audio for better MP3 compatibility
                try {
                    console.log('Trying HTML5 Audio fallback...');
                    const audioBlob = audioData instanceof Blob ? audioData : new Blob([audioData], { type: 'audio/mpeg' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    const audio = new Audio(audioUrl);
                    
                    return new Promise((resolve) => {
                        audio.onended = () => {
                            URL.revokeObjectURL(audioUrl);
                            console.log('HTML5 Audio playback completed');
                            resolve();
                        };
                        audio.onerror = (e) => {
                            console.error('HTML5 Audio error:', e);
                            URL.revokeObjectURL(audioUrl);
                            resolve();
                        };
                        audio.play().catch(e => {
                            console.error('HTML5 play failed:', e);
                            URL.revokeObjectURL(audioUrl);
                            resolve();
                        });
                    });
                } catch (fallbackError) {
                    console.error('Fallback also failed:', fallbackError);
                }
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
