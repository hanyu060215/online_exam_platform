/**
 * Exam Monitoring System
 * This script monitors student activity during exams to prevent cheating
 */

class ExamMonitor {
    constructor() {
        this.focusEvents = [];
        this.suspiciousActivities = [];
        this.lastActiveTime = Date.now();
        this.isHidden = false;
        this.captureInterval = null;
        this.monitoringActive = false;
        this.copyPasteCount = 0;
        this.username = '';
        this.violationCount = 0;
        this.maxViolations = 5;
        this.warningElement = null;
        
        // Tracking for reduced sensitivity
        this.tabSwitchTime = 0;
        this.minTabAwayTime = 3000; // Minimum 3 seconds away to count as violation
        this.lastViolationTime = 0;
        this.minViolationInterval = 5000; // Minimum 5 seconds between violations
    }

    /**
     * Initialize the monitoring system
     */
    init(username) {
        this.username = username;
        this.monitoringActive = true;
        console.log('Exam monitoring initialized for user:', username);
        
        // Create warning element but don't show it yet
        this.createWarningElement();
        
        // Add a small delay before setting up event listeners to avoid initial false positives
        setTimeout(() => {
            this.setupEventListeners();
            this.startPeriodicReporting();
            this.startHeartbeat();
            
            // Send initial status (but don't count as violation)
            this.reportActivity('exam_started', {}, false);
        }, 1500); // 1.5 second delay to avoid initial false positives
    }

    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        // Tab visibility change detection (with more robust handling)
        document.addEventListener('visibilitychange', () => this.handleVisibilityChange());
        
        // Window focus/blur detection
        window.addEventListener('focus', () => this.handleFocusChange(true));
        window.addEventListener('blur', () => this.handleFocusChange(false));
        
        // Additional mouseleave detection for more reliable tab switching detection
        document.addEventListener('mouseleave', () => this.handleMouseLeave());
        
        // Copy-paste detection
        document.addEventListener('copy', () => this.handleCopyPaste('copy'));
        document.addEventListener('paste', () => this.handleCopyPaste('paste'));
        
        // Keyboard shortcuts detection
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        // Periodic check for activity
        setInterval(() => this.checkActivity(), 5000);
        
        // Store initial window state
        this.isHidden = document.hidden;
    }

    /**
     * Handle visibility change (tab switching)
     */
    handleVisibilityChange() {
        const isHidden = document.hidden;
        const timestamp = Date.now();
        
        if (isHidden !== this.isHidden) {
            // Log for debugging
            console.log(`Visibility changed: ${isHidden ? 'hidden' : 'visible'} at ${new Date(timestamp).toLocaleTimeString()}`);
            
            this.isHidden = isHidden;
            const action = isHidden ? 'tab_hidden' : 'tab_visible';
            this.recordEvent(action);
            
            if (isHidden) {
                // Just record the time when tab becomes hidden
                this.tabSwitchTime = timestamp;
            } else if (this.tabSwitchTime > 0) {
                // Only report as suspicious if away for more than minTabAwayTime
                const timeAway = timestamp - this.tabSwitchTime;
                if (timeAway > this.minTabAwayTime) {
                    this.reportActivity('tab_switch', {
                        timestamp: timestamp,
                        timeAway: timeAway,
                        description: `Student switched away from exam tab for ${Math.round(timeAway/1000)} seconds`
                    });
                } else {
                    // For very brief switches, just record but don't count as violation
                    this.recordEvent('brief_tab_switch');
                }
                this.tabSwitchTime = 0;
            }
        }
    }
    
    /**
     * Handle mouse leaving the document - additional detection for tab switching
     */
    handleMouseLeave() {
        // Only consider it if the tab isn't already hidden
        if (!this.isHidden) {
            // Mouse leaving could indicate tab/window switching
            const timestamp = Date.now();
            this.recordEvent('mouse_left_window');
            
            // Start timing but don't report yet (will report if gone for minTabAwayTime)
            if (this.tabSwitchTime === 0) {
                this.tabSwitchTime = timestamp;
                console.log('Mouse left window - started tracking potential switch');
            }
        }
    }

    /**
     * Handle window focus/blur events
     */
    handleFocusChange(isFocused) {
        const timestamp = Date.now();
        const action = isFocused ? 'window_focus' : 'window_blur';
        this.recordEvent(action);
        
        // Only report focus lost if not already counting a tab switch
        // This prevents double-counting when both events fire together
        if (!isFocused && !this.isHidden && timestamp - this.tabSwitchTime > 1000) {
            this.reportActivity('focus_lost', {
                timestamp: timestamp,
                description: 'Student switched to another application'
            });
        }
    }

    /**
     * Handle copy and paste events
     */
    handleCopyPaste(action) {
        this.copyPasteCount++;
        this.recordEvent(action);
        
        if (this.copyPasteCount > 3) {
            this.reportActivity('excessive_copy_paste', {
                count: this.copyPasteCount,
                description: 'Student performed multiple copy-paste actions'
            });
        }
    }

    /**
     * Monitor keyboard shortcuts that could be used for cheating
     */
    handleKeyDown(e) {
        // Check for potential cheating keyboard shortcuts
        if ((e.ctrlKey || e.metaKey) && 
            (e.key === 'c' || e.key === 'v' || e.key === 'f' || 
             e.key === 'p' || e.key === 'a')) {
            
            this.recordEvent('shortcut_' + e.key);
            
            // For certain shortcuts, we might want to prevent them
            if (e.key === 'p') { // Prevent printing
                e.preventDefault();
                this.reportActivity('print_attempt', {
                    description: 'Student attempted to print the exam'
                });
            }
        }
    }

    /**
     * Record an event with timestamp
     */
    recordEvent(action) {
        const timestamp = Date.now();
        this.focusEvents.push({
            action,
            timestamp,
            timeAway: this.isHidden ? (timestamp - this.lastActiveTime) : 0
        });
        
        if (!this.isHidden) {
            this.lastActiveTime = timestamp;
        }
    }

    /**
     * Periodically check for suspicious inactivity
     */
    checkActivity() {
        if (!this.monitoringActive) return;
        
        const currentTime = Date.now();
        const timeSinceLastActive = currentTime - this.lastActiveTime;
        
        // If inactive for more than 2 minutes (increased from 1 minute)
        if (this.isHidden && timeSinceLastActive > 120000) {
            this.reportActivity('extended_absence', {
                timeAway: Math.round(timeSinceLastActive / 1000),
                description: 'Student away from exam for extended period'
            });
        }
    }

    /**
     * Start periodic activity reporting to server
     */
    startPeriodicReporting() {
        // Report activity every 30 seconds
        this.reportingInterval = setInterval(() => {
            // Always send regular updates, even if no new events
            this.reportActivityBatch();
        }, 30000);
    }
    
    /**
     * Start heartbeat to keep server updated about user activity
     */
    startHeartbeat() {
        // Send heartbeat every 15 seconds
        this.heartbeatInterval = setInterval(() => {
            if (this.monitoringActive) {
                this.recordEvent('heartbeat');
                // Update last active time
                this.lastActiveTime = Date.now();
            }
        }, 15000);
    }

    /**
     * Report a single suspicious activity to the server
     * @param {string} activityType - Type of activity
     * @param {Object} details - Additional details
     * @param {boolean} countAsViolation - Whether to count as a violation (default: true)
     */
    reportActivity(activityType, details = {}, countAsViolation = true) {
        if (!this.monitoringActive) return;
        
        const activity = {
            type: activityType,
            timestamp: Date.now(),
            username: this.username,
            ...details
        };
        
        this.suspiciousActivities.push(activity);
        
        // Only increment violation count and show warning for suspicious activities
        // AND only if countAsViolation is true (to exclude initial activities)
        if (countAsViolation && 
            ['tab_switch', 'focus_lost', 'extended_absence', 'excessive_copy_paste', 'print_attempt'].includes(activityType)) {
            this.handleViolation(activityType);
        }
        
        // Send immediately for critical activities
        fetch('/report_activity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(activity)
        }).catch(error => {
            console.error('Failed to report activity:', error);
        });
    }

    /**
     * Send batched activity data to server
     */
    reportActivityBatch() {
        // Always send a heartbeat, even if there are no events to report
        if (!this.monitoringActive) return;
        
        // If no events at all, add a heartbeat event
        if (this.focusEvents.length === 0) {
            this.recordEvent('heartbeat');
        }
        
        const payload = {
            username: this.username,
            events: this.focusEvents,
            suspiciousActivities: this.suspiciousActivities,
            timestamp: Date.now() // Include current timestamp
        };
        
        fetch('/report_activity_batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        })
        .then(response => {
            if (response.ok) {
                // Clear recorded events after successful submission
                this.focusEvents = [];
                this.suspiciousActivities = [];
            }
        })
        .catch(error => {
            console.error('Failed to send activity batch:', error);
        });
    }

    /**
     * Stop monitoring
     */
    stop() {
        // Send final activity
        this.reportActivity('exam_ended');
        
        // Send any remaining batched events
        this.reportActivityBatch();
        
        // Clear intervals
        clearInterval(this.reportingInterval);
        clearInterval(this.heartbeatInterval);
        
        this.monitoringActive = false;
        console.log('Exam monitoring stopped');
        
        // Hide warning if showing
        if (this.warningElement) {
            this.warningElement.style.display = 'none';
        }
    }
    
    /**
     * Handle violations and auto-submit after max violations
     */
    handleViolation(activityType) {
        const now = Date.now();
        
        // Enforce minimum time between counting violations to prevent rapid counting
        if (now - this.lastViolationTime < this.minViolationInterval) {
            console.log('Violation detected but too soon after previous violation - not counting');
            return;
        }
        
        this.violationCount++;
        this.lastViolationTime = now;
        const remainingAttempts = this.maxViolations - this.violationCount;
        
        console.log(`Violation #${this.violationCount} of type ${activityType} recorded. ${remainingAttempts} attempts remaining.`);
        
        // Map activity type to human-readable violation
        const violationType = {
            'tab_switch': 'switching tabs',
            'focus_lost': 'leaving the exam window',
            'extended_absence': 'being absent for too long',
            'excessive_copy_paste': 'excessive copy-paste activity',
            'print_attempt': 'attempting to print'
        }[activityType] || 'suspicious behavior';
        
        // Show warning
        this.showWarning(violationType, remainingAttempts);
        
        // If max violations reached, submit the exam
        if (this.violationCount >= this.maxViolations) {
            this.forceSubmitExam();
        }
    }
    
    /**
     * Create warning element
     */
    createWarningElement() {
        // Create warning element if it doesn't exist
        if (!this.warningElement) {
            const warningElement = document.createElement('div');
            warningElement.className = 'exam-warning';
            warningElement.style.cssText = `
                display: none;
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background-color: #ffebee;
                border: 2px solid #f44336;
                border-radius: 4px;
                padding: 15px 20px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                z-index: 9999;
                text-align: center;
                font-family: Arial, sans-serif;
            `;
            
            const warningContent = document.createElement('div');
            warningContent.className = 'warning-content';
            warningElement.appendChild(warningContent);
            
            const closeButton = document.createElement('button');
            closeButton.textContent = 'OK';
            closeButton.style.cssText = `
                margin-top: 10px;
                padding: 5px 15px;
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            `;
            closeButton.onclick = () => {
                warningElement.style.display = 'none';
            };
            warningElement.appendChild(closeButton);
            
            document.body.appendChild(warningElement);
            this.warningElement = warningElement;
        }
    }
    
    /**
     * Show warning popup
     */
    showWarning(violationType, remainingAttempts) {
        const warningContent = this.warningElement.querySelector('.warning-content');
        
        if (remainingAttempts <= 0) {
            warningContent.innerHTML = `<strong>Warning!</strong><br>
                You have reached the maximum number of violations.<br>
                Your exam is being submitted automatically.`;
        } else {
            warningContent.innerHTML = `<strong>Warning!</strong><br>
                Suspicious activity detected: ${violationType}.<br>
                Please do not do that again. <br>
                ${remainingAttempts} attempt${remainingAttempts !== 1 ? 's' : ''} remaining before exam auto-submission.`;
        }
        
        this.warningElement.style.display = 'block';
        
        // Auto hide after 10 seconds if not closed manually
        setTimeout(() => {
            if (this.warningElement) {
                this.warningElement.style.display = 'none';
            }
        }, 10000);
    }
    
    /**
     * Force submit the exam
     */
    forceSubmitExam() {
        // Report that the exam was force-submitted
        this.reportActivity('exam_force_submitted', {
            description: 'Exam auto-submitted due to multiple violations'
        });
        
        // Make request to force submit the exam
        fetch('/force_submit_exam', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: this.username,
                violations: this.violationCount
            })
        })
        .then(response => {
            if (response.ok) {
                // Redirect to a page indicating the exam was force-submitted
                window.location.href = '/exam_force_submitted';
            }
        })
        .catch(error => {
            console.error('Failed to force submit exam:', error);
        });
    }
}

// Create global instance
const examMonitor = new ExamMonitor();

// Export for use in other scripts
window.examMonitor = examMonitor;
