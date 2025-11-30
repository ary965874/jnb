class SessionGenerator {
    constructor() {
        this.currentStep = 1;
        this.sessionData = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.showStep(1);
    }

    bindEvents() {
        // Form submissions
        document.getElementById('phoneForm').addEventListener('submit', (e) => this.handlePhoneSubmit(e));
        document.getElementById('otpForm').addEventListener('submit', (e) => this.handleOtpSubmit(e));
        
        // Navigation
        document.getElementById('backToStep1').addEventListener('click', () => this.showStep(1));
        document.getElementById('newSessionBtn').addEventListener('click', () => this.resetForm());
        
        // Auto-submit OTP
        document.getElementById('otpCode').addEventListener('input', (e) => {
            if (e.target.value.length === 5) {
                setTimeout(() => document.getElementById('verifyOtpBtn').click(), 300);
            }
        });

        // Only allow numbers in OTP
        document.getElementById('otpCode').addEventListener('keypress', (e) => {
            if (!/[0-9]/.test(e.key)) {
                e.preventDefault();
            }
        });
    }

    showStep(step) {
        // Hide all steps
        document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
        document.querySelectorAll('.step-item').forEach(s => s.classList.remove('active', 'completed'));
        
        // Show current step
        document.getElementById(`step${step}`).classList.add('active');
        
        // Update step indicator
        for (let i = 1; i <= step; i++) {
            const indicator = document.getElementById(`step${i}-indicator`);
            if (i === step) {
                indicator.classList.add('active');
            } else {
                indicator.classList.add('completed');
            }
        }
        
        this.currentStep = step;
        
        // Auto-focus on first input
        setTimeout(() => {
            const firstInput = document.querySelector(`#step${step} input`);
            if (firstInput) firstInput.focus();
        }, 300);
    }

    showLoading(text = 'Processing...') {
        document.getElementById('loadingText').textContent = text;
        document.getElementById('loading').style.display = 'block';
    }

    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `info-card ${type}`;
        notification.innerHTML = `
            <h4>${type === 'error' ? '❌ Error' : type === 'success' ? '✅ Success' : 'ℹ️ Info'}</h4>
            <p>${message}</p>
        `;
        
        // Add to container
        const container = document.querySelector('.step.active');
        container.insertBefore(notification, container.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    async handlePhoneSubmit(e) {
        e.preventDefault();
        
        const phone = document.getElementById('phone').value.trim();
        
        if (!phone) {
            this.showError('Please enter your phone number');
            return;
        }

        this.showLoading('Sending verification code...');
        this.disableForm('phoneForm');

        try {
            const response = await fetch('/api/request-code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ phone })
            });

            const data = await response.json();

            if (data.success) {
                this.sessionData = {
                    phone: phone,
                    phone_code_hash: data.phone_code_hash
                };
                this.showStep(2);
                this.showSuccess('Verification code sent successfully!');
            } else {
                this.showError(data.error || 'Failed to send verification code');
            }
        } catch (error) {
            this.showError('Network error: ' + error.message);
        } finally {
            this.hideLoading();
            this.enableForm('phoneForm');
        }
    }

    async handleOtpSubmit(e) {
        e.preventDefault();
        
        const code = document.getElementById('otpCode').value.trim();
        const password = document.getElementById('password').value.trim();

        if (!this.sessionData) {
            this.showError('Session expired. Please start over.');
            return;
        }

        if (!code || code.length !== 5) {
            this.showError('Please enter a valid 5-digit verification code');
            return;
        }

        this.showLoading('Verifying code and generating session...');
        this.disableForm('otpForm');

        try {
            const response = await fetch('/api/verify-code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    ...this.sessionData,
                    code: code,
                    password: password
                })
            });

            const data = await response.json();

            if (data.success) {
                document.getElementById('sessionString').textContent = data.session_string;
                this.showStep(3);
                document.getElementById('step3').classList.add('success-pulse');
                this.showSuccess('Session generated successfully!');
            } else {
                if (data.error === '2FA_PASSWORD_REQUIRED') {
                    document.getElementById('passwordField').style.display = 'block';
                    this.showError('2FA password required. Please enter your password.');
                } else {
                    this.showError(data.error || 'Verification failed');
                }
            }
        } catch (error) {
            this.showError('Network error: ' + error.message);
        } finally {
            this.hideLoading();
            this.enableForm('otpForm');
        }
    }

    disableForm(formId) {
        const form = document.getElementById(formId);
        const buttons = form.querySelectorAll('button');
        buttons.forEach(btn => btn.disabled = true);
    }

    enableForm(formId) {
        const form = document.getElementById(formId);
        const buttons = form.querySelectorAll('button');
        buttons.forEach(btn => btn.disabled = false);
    }

    resetForm() {
        // Reset forms
        document.getElementById('phoneForm').reset();
        document.getElementById('otpForm').reset();
        
        // Hide password field
        document.getElementById('passwordField').style.display = 'none';
        
        // Reset session data
        this.sessionData = null;
        
        // Remove success animation
        document.getElementById('step3').classList.remove('success-pulse');
        
        // Show first step
        this.showStep(1);
        
        this.showSuccess('Ready to generate a new session!');
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new SessionGenerator();
});

// Add some interactive effects
document.addEventListener('DOMContentLoaded', () => {
    // Add floating animation to logo
    const logo = document.querySelector('.logo');
    if (logo) {
        setInterval(() => {
            logo.style.transform = 'translateY(-5px)';
            setTimeout(() => {
                logo.style.transform = 'translateY(0px)';
            }, 1500);
        }, 3000);
    }
});