// Camera functionality for add_subject.html with permission handling
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const captureBtn = document.getElementById('captureBtn');
const imageDataInput = document.getElementById('imageData');
const preview = document.getElementById('preview');
const capturedImage = document.getElementById('capturedImage');
const submitBtn = document.getElementById('submitBtn');
const permissionInstructions = document.getElementById('permissionInstructions');
const requestPermissionBtn = document.getElementById('requestPermissionBtn');
const cameraStatus = document.getElementById('cameraStatus');
const statusDetails = document.getElementById('statusDetails');

let stream = null;
let currentZoom = 1;
let digitalZoom = 1;
let useDigitalZoom = false;
let faceDetectionInterval = null;
let permissionDenied = false;

// Update camera status display
function updateCameraStatus(status, message, type = 'info') {
    if (cameraStatus) {
        cameraStatus.className = `alert alert-${type}`;
        statusDetails.innerHTML = message;
    }
}

// Request camera permission explicitly
async function requestCameraPermission() {
    try {
        updateCameraStatus('requesting', 'Requesting camera permission...', 'info');
        
        // Try to get camera stream
        const testStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        
        // If successful, stop the test stream and start the actual camera
        testStream.getTracks().forEach(track => track.stop());
        
        // Hide permission instructions
        permissionInstructions.style.display = 'none';
        
        // Start the actual camera
        startCamera();
        
    } catch (error) {
        console.error('Permission request failed:', error);
        
        if (error.name === 'NotAllowedError') {
            updateCameraStatus('denied', 
                'Camera permission denied. Please check your browser settings and allow camera access for this site.', 
                'danger'
            );
            showPermissionInstructions();
        } else if (error.name === 'NotFoundError') {
            updateCameraStatus('not-found', 
                'No camera device found. Please connect a camera and refresh the page.', 
                'warning'
            );
        } else {
            updateCameraStatus('error', 
                `Camera error: ${error.message}`, 
                'danger'
            );
        }
    }
}

// Show permission instructions
function showPermissionInstructions() {
    permissionInstructions.style.display = 'block';
    video.style.display = 'none';
    
    // Update indicator
    const indicator = document.getElementById('faceIndicator');
    if (indicator) {
        indicator.className = 'badge bg-danger';
        indicator.textContent = 'Permission Required';
    }
}

// Check camera permission status
async function checkCameraPermission() {
    try {
        // Check if permissions API is available
        if ('permissions' in navigator) {
            const result = await navigator.permissions.query({ name: 'camera' });
            console.log('Camera permission status:', result.state);
            
            if (result.state === 'denied') {
                permissionDenied = true;
                showPermissionInstructions();
                updateCameraStatus('denied', 
                    'Camera access is blocked. Please follow the instructions below to enable camera access.', 
                    'danger'
                );
                return false;
            } else if (result.state === 'prompt') {
                updateCameraStatus('prompt', 
                    'Camera permission will be requested when you click "Allow Camera Access".', 
                    'warning'
                );
                showPermissionInstructions();
                return false;
            }
            
            return true;
        }
        
        // If permissions API not available, try directly
        return true;
        
    } catch (error) {
        console.log('Permissions API not supported, trying direct access');
        return true;
    }
}

// Start camera with zoom capabilities
async function startCamera() {
    try {
        // Hide permission instructions if visible
        permissionInstructions.style.display = 'none';
        video.style.display = 'block';
        
        // Update indicator
        const indicator = document.getElementById('faceIndicator');
        if (indicator) {
            indicator.className = 'badge bg-info';
            indicator.textContent = 'Starting Camera...';
        }
        
        updateCameraStatus('starting', 'Starting camera...', 'info');
        
        // Stop any existing stream
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
        
        // Request camera with multiple fallback options
        const constraints = {
            video: {
                width: { ideal: 1280 },
                height: { ideal: 720 },
                facingMode: 'user'
            },
            audio: false
        };
        
        try {
            stream = await navigator.mediaDevices.getUserMedia(constraints);
        } catch (error) {
            console.log('Ideal constraints failed, trying basic constraints');
            stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        }
        
        video.srcObject = stream;
        
        // Check if hardware zoom is supported
        const [track] = stream.getVideoTracks();
        const settings = track.getSettings();
        const capabilities = track.getCapabilities ? track.getCapabilities() : {};
        
        console.log('Track settings:', settings);
        console.log('Track capabilities:', capabilities);
        
        updateCameraStatus('active', 
            `Camera active: ${settings.deviceId ? 'Device ' + settings.deviceId.substring(0, 8) + '...' : 'Default camera'}`, 
            'success'
        );
        
        // Setup zoom controls
        if (capabilities && capabilities.zoom && capabilities.zoom.max > capabilities.zoom.min) {
            console.log('Hardware zoom available');
            setupZoomControls(track, capabilities.zoom, false);
        } else {
            console.log('Hardware zoom not available, using digital zoom');
            setupZoomControls(null, { min: 1, max: 3, step: 0.1 }, true);
        }
        
        // Ensure video plays
        video.onloadedmetadata = () => {
            video.play()
                .then(() => {
                    console.log('Video playing successfully');
                    if (indicator) {
                        indicator.className = 'badge bg-success';
                        indicator.textContent = 'Camera Ready';
                    }
                    startFaceDetection();
                })
                .catch(err => {
                    console.error('Error playing video:', err);
                    if (indicator) {
                        indicator.className = 'badge bg-warning';
                        indicator.textContent = 'Click Video to Start';
                    }
                    // Add click to play
                    video.addEventListener('click', () => {
                        video.play();
                    }, { once: true });
                });
        };
        
        // Add attributes for compatibility
        video.setAttribute('playsinline', true);
        video.setAttribute('autoplay', true);
        video.setAttribute('muted', true);
        
    } catch (err) {
        console.error('Error accessing camera:', err);
        
        let errorMessage = '';
        let statusType = 'danger';
        
        if (err.name === 'NotAllowedError') {
            errorMessage = 'Camera permission denied. Click "Allow Camera Access" button above and allow access when prompted.';
            showPermissionInstructions();
        } else if (err.name === 'NotFoundError') {
            errorMessage = 'No camera found. Please connect a camera and reload the page.';
            statusType = 'warning';
        } else if (err.name === 'NotReadableError') {
            errorMessage = 'Camera is already in use by another application. Please close other apps using the camera.';
        } else if (err.name === 'OverconstrainedError') {
            errorMessage = 'Camera does not support the requested settings.';
        } else {
            errorMessage = err.message || 'Unknown error occurred.';
        }
        
        updateCameraStatus('error', errorMessage, statusType);
        
        const indicator = document.getElementById('faceIndicator');
        if (indicator) {
            indicator.className = 'badge bg-danger';
            indicator.textContent = 'Camera Error';
        }
    }
}

// Setup zoom controls (rest of the function remains the same)
function setupZoomControls(track, zoomCapabilities, isDigital = false) {
    const { min, max, step } = zoomCapabilities;
    useDigitalZoom = isDigital;
    
    // Remove any existing zoom controls
    const existingControls = document.querySelector('.zoom-controls');
    if (existingControls) {
        existingControls.remove();
    }
    
    // Add zoom controls to the UI
    const zoomControls = document.createElement('div');
    zoomControls.className = 'zoom-controls mt-2';
    zoomControls.innerHTML = `
        <div class="alert alert-info mb-2">
            <div class="d-flex">
                <div>
                    <svg xmlns="http://www.w3.org/2000/svg" class="icon alert-icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none">
                        <path stroke="none" d="M0 0h24v24H0z" fill="none"></path>
                        <circle cx="12" cy="12" r="9"></circle>
                        <line x1="12" y1="8" x2="12" y2="12"></line>
                        <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                </div>
                <div>
                    <div class="text-muted">
                        ${isDigital ? 'Using digital zoom (camera hardware zoom not available)' : 'Camera hardware zoom available'}
                    </div>
                </div>
            </div>
        </div>
        <div class="d-flex align-items-center gap-2">
            <button type="button" class="btn btn-sm btn-secondary" id="zoomOut">
                <i class="ti ti-zoom-out"></i>
            </button>
            <input type="range" id="zoomSlider" class="form-range flex-fill" 
                min="${min}" max="${max}" step="${step || 0.1}" value="1">
            <button type="button" class="btn btn-sm btn-secondary" id="zoomIn">
                <i class="ti ti-zoom-in"></i>
            </button>
            <button type="button" class="btn btn-sm btn-info" id="autoFrame">
                <i class="ti ti-focus-2"></i> Auto Frame
            </button>
        </div>
        <small class="text-muted">Zoom: <span id="zoomValue">1.0x</span></small>
    `;
    
    // Insert after video
    video.parentElement.appendChild(zoomControls);
    
    const zoomSlider = document.getElementById('zoomSlider');
    const zoomValue = document.getElementById('zoomValue');
    const zoomIn = document.getElementById('zoomIn');
    const zoomOut = document.getElementById('zoomOut');
    const autoFrame = document.getElementById('autoFrame');
    
    // Apply zoom function
    const applyZoom = (zoomLevel) => {
        if (useDigitalZoom) {
            digitalZoom = zoomLevel;
            video.style.transform = `scale(${digitalZoom})`;
            video.style.transformOrigin = 'center center';
        } else if (track) {
            track.applyConstraints({ advanced: [{ zoom: zoomLevel }] })
                .then(() => {
                    console.log('Hardware zoom applied:', zoomLevel);
                })
                .catch(err => {
                    console.error('Failed to apply hardware zoom:', err);
                    // Fall back to digital zoom
                    useDigitalZoom = true;
                    digitalZoom = zoomLevel;
                    video.style.transform = `scale(${digitalZoom})`;
                });
        }
        currentZoom = zoomLevel;
        zoomValue.textContent = zoomLevel.toFixed(1) + 'x';
    };
    
    // Zoom slider handler
    zoomSlider.addEventListener('input', (e) => {
        applyZoom(parseFloat(e.target.value));
    });
    
    // Zoom buttons
    zoomIn.addEventListener('click', () => {
        const newZoom = Math.min(currentZoom + (step || 0.1), max);
        zoomSlider.value = newZoom;
        applyZoom(newZoom);
    });
    
    zoomOut.addEventListener('click', () => {
        const newZoom = Math.max(currentZoom - (step || 0.1), min);
        zoomSlider.value = newZoom;
        applyZoom(newZoom);
    });
    
    // Auto-frame button
    autoFrame.addEventListener('click', () => {
        autoFrameFace();
    });
}

// Rest of the functions remain the same...
// (detectFaceInCanvas, autoFrameFace, startFaceDetection, capture photo, etc.)

// Simple face detection using canvas
function detectFaceInCanvas() {
    if (!video.videoWidth || !video.videoHeight) return null;
    
    const tempCanvas = document.createElement('canvas');
    const tempCtx = tempCanvas.getContext('2d');
    
    tempCanvas.width = video.videoWidth;
    tempCanvas.height = video.videoHeight;
    tempCtx.drawImage(video, 0, 0);
    
    const centerX = tempCanvas.width / 2;
    const centerY = tempCanvas.height / 2;
    const regionSize = Math.min(tempCanvas.width, tempCanvas.height) * 0.6;
    
    const imageData = tempCtx.getImageData(
        centerX - regionSize/2, 
        centerY - regionSize/2, 
        regionSize, 
        regionSize
    );
    
    const data = imageData.data;
    let skinPixels = 0;
    
    for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        
        if (r > 95 && g > 40 && b > 20 &&
            r > g && r > b &&
            Math.abs(r - g) > 15) {
            skinPixels++;
        }
    }
    
    const totalPixels = (data.length / 4);
    const skinPercentage = (skinPixels / totalPixels) * 100;
    
    if (skinPercentage > 5) {
        return {
            detected: true,
            confidence: Math.min(skinPercentage * 5, 100)
        };
    }
    
    return { detected: false, confidence: 0 };
}

// Auto-frame face
function autoFrameFace() {
    const face = detectFaceInCanvas();
    
    if (face && face.detected) {
        const targetZoom = useDigitalZoom ? 1.5 : 1.8;
        
        const zoomSlider = document.getElementById('zoomSlider');
        if (zoomSlider) {
            zoomSlider.value = targetZoom;
            
            if (useDigitalZoom) {
                digitalZoom = targetZoom;
                video.style.transform = `scale(${digitalZoom})`;
                currentZoom = targetZoom;
            } else {
                const [track] = stream.getVideoTracks();
                if (track) {
                    track.applyConstraints({ advanced: [{ zoom: targetZoom }] })
                        .catch(err => console.error('Auto zoom failed:', err));
                }
                currentZoom = targetZoom;
            }
            
            document.getElementById('zoomValue').textContent = targetZoom.toFixed(1) + 'x';
        }
        
        const autoFrame = document.getElementById('autoFrame');
        if (autoFrame) {
            autoFrame.classList.add('btn-success');
            setTimeout(() => {
                autoFrame.classList.remove('btn-success');
                autoFrame.classList.add('btn-info');
            }, 1000);
        }
    } else {
        alert('No face detected. Please position your face in the center of the frame.');
    }
}

// Start continuous face detection
function startFaceDetection() {
    faceDetectionInterval = setInterval(() => {
        const face = detectFaceInCanvas();
        
        const indicator = document.getElementById('faceIndicator');
        if (indicator && face) {
            if (face.detected) {
                indicator.className = 'badge bg-success';
                indicator.textContent = 'Face Detected';
            } else {
                indicator.className = 'badge bg-warning';
                indicator.textContent = 'Position Face in Center';
            }
        }
    }, 500);
}

// Capture photo
captureBtn.addEventListener('click', () => {
    if (video.videoWidth && video.videoHeight) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        if (useDigitalZoom && digitalZoom > 1) {
            const cropSize = 1 / digitalZoom;
            const sx = (video.videoWidth * (1 - cropSize)) / 2;
            const sy = (video.videoHeight * (1 - cropSize)) / 2;
            const sw = video.videoWidth * cropSize;
            const sh = video.videoHeight * cropSize;
            
            ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
        } else {
            ctx.drawImage(video, 0, 0);
        }
        
        const imageData = canvas.toDataURL('image/jpeg', 0.95);
        
        console.log('Image captured with zoom:', currentZoom);
        
        imageDataInput.value = imageData;
        capturedImage.src = imageData;
        preview.style.display = 'block';
        submitBtn.disabled = false;
    } else {
        alert('Please wait for camera to initialize');
    }
});

// Event Listeners
if (requestPermissionBtn) {
    requestPermissionBtn.addEventListener('click', requestCameraPermission);
}

// Form validation
document.getElementById('addSubjectForm').addEventListener('submit', function(e) {
    if (!imageDataInput.value) {
        e.preventDefault();
        alert('Please capture a photo first');
        return false;
    }
});

// Initialize camera when DOM is ready
async function initialize() {
    const hasPermission = await checkCameraPermission();
    if (hasPermission) {
        startCamera();
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    if (faceDetectionInterval) {
        clearInterval(faceDetectionInterval);
    }
});

// Debug: Check video state
video.addEventListener('loadeddata', () => {
    console.log('Video loaded successfully');
    console.log('Video dimensions:', video.videoWidth, 'x', video.videoHeight);
});

video.addEventListener('error', (e) => {
    console.error('Video error:', e);
});