/**
 * main.js
 * Consolidated logic for Delstarford Works
 */

// 1. INITIALIZE FIREBASE (Safety Check)
if (typeof firebase !== 'undefined' && !firebase.apps.length) {
    console.warn("Firebase config not found in main.js scope. Relying on base.html initialization.");
}

document.addEventListener('DOMContentLoaded', () => {
    console.log("Delstarford Works Engine Initialized...");

    // A. Run Global UI Scripts
    initNavigation();
    initScrollAnimations();

    // B. Run Page-Specific Scripts (Only execute if the elements exist on the current page)
    if (document.getElementById('totalPrice')) initPriceEstimator();
    if (document.getElementById('requestForm')) initContactForm();
    
    // Safety check in case initGeneralContactForm is defined in another file
    if (document.getElementById('contactForm') && typeof initGeneralContactForm === 'function') {
        initGeneralContactForm();
    }

    // C. AUTHENTICATION LOGIC
    if (typeof firebase !== 'undefined') {
        const auth = firebase.auth();
        
        auth.onAuthStateChanged((user) => {
            const securityScreen = document.getElementById('security-screen');
            const mainDashboard = document.getElementById('main-dashboard');
            const currentPath = window.location.pathname;

            // Define which pages REQUIRE login
            const protectedPages = ['/dashboard', '/admin', '/ai-lab-secure'];
            const isProtected = protectedPages.some(page => currentPath.includes(page));

            if (user) {
                // --- USER IS LOGGED IN ---
                console.log("User Logged In:", user.email);

                // 1. If on Login page, send them to Dashboard (Quality of Life)
                if (currentPath === '/login' || currentPath === '/register') {
                    window.location.href = "/dashboard";
                    return;
                }

                // 2. Unlock Dashboard UI if it exists on this page
                if (securityScreen) securityScreen.style.display = 'none';
                if (mainDashboard) mainDashboard.style.display = 'flex';

                // 3. Load Data
                initRealDashboard(user);

            } else {
                // --- USER IS NOT LOGGED IN ---
                console.log("Guest User");

                if (isProtected) {
                    // 1. If on a protected page, kick them out
                    console.log("Restricted Area. Redirecting to Login.");
                    sessionStorage.setItem('redirectAfterLogin', currentPath);
                    window.location.href = "/login";
                } else {
                    // 2. If on Public page (Home, Login, etc), DO NOTHING.
                    if (securityScreen) securityScreen.style.display = 'none';
                }
            }
        });
    }
});


/* =========================================
   HELPER FUNCTIONS
   ========================================= */

// Navigation Scroll Effect
function initNavigation() {
    const navbar = document.querySelector('.navbar') || document.querySelector('.site-header');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) navbar.classList.add('navbar-scrolled', 'scrolled');
            else navbar.classList.remove('navbar-scrolled', 'scrolled');
        });
    }
}

// Fade-in Animations
function initScrollAnimations() {
    if (typeof IntersectionObserver === 'undefined') return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.scroll-trigger, .hero-content').forEach(el => observer.observe(el));
}

// Dashboard Data Population (with Auto-Setup for New Users)
function initRealDashboard(user) {
    if (!document.getElementById('project-status-text')) return;

    const db = firebase.database();
    const uid = user.uid;

    // 1. PROFILE NAME FIX
    const nameEl = document.getElementById('display-name');
    const emailEl = document.getElementById('display-email');
    
    // Extract "delstarford" from "delstarford@gmail.com" safely
    const fallbackName = user.email ? user.email.split('@')[0] : "User"; 
    const finalName = user.displayName || fallbackName.charAt(0).toUpperCase() + fallbackName.slice(1);

    if(nameEl) nameEl.innerText = finalName;
    if(emailEl) emailEl.innerText = user.email;

    // 2. CHECK & CREATE DEFAULT DATA (The "Empty Dashboard" Fix)
    const userRef = db.ref(`users/${uid}`);
    
    userRef.once('value', (snapshot) => {
        if (!snapshot.exists()) {
            console.log("New user detected! Initializing database...");
            // Create default data so the dashboard isn't empty
            userRef.set({
                profile: {
                    name: finalName,
                    email: user.email,
                    joined: new Date().toISOString()
                },
                activity: {
                    welcome_msg: {
                        message: "🎉 Welcome to Delstarford Works! Your account is active.",
                        time: new Date().toLocaleString()
                    }
                },
                licenses: {
                    starter_pack: "Free Tier" 
                },
                role: 'member' // Assign basic role securely
            });
            
            // Set a default project status
            db.ref(`active_projects/${uid}`).set({
                status: "Pending Setup",
                progress: 10,
                name: "Onboarding"
            });
        }
    });

    // 3. LISTEN FOR LIVE DATA
    
    // Projects
    db.ref(`active_projects/${uid}`).on('value', (s) => {
        const d = s.val();
        const statusText = document.getElementById('project-status-text');
        const progressBar = document.getElementById('project-progress');
        
        if(statusText) statusText.innerText = d ? (d.status || "Active") : "No Active Projects";
        if(progressBar) progressBar.style.width = d ? (d.progress + "%") : "0%";
        
        if (statusText && d) {
            statusText.className = "font-bold " + (d.status === "Completed" ? "text-green-600" : "text-blue-600");
        }
    });

    // Licenses
    db.ref(`users/${uid}/licenses`).on('value', s => {
        const el = document.getElementById('license-count');
        if(el) el.innerText = s.exists() ? Object.keys(s.val()).length : 0;
    });

    // Activity Feed
    db.ref(`users/${uid}/activity`).limitToLast(5).on('value', (s) => {
        const rows = document.getElementById('activity-rows');
        if (!rows) return;
        
        rows.innerHTML = ""; 
        
        if (!s.exists()) {
            rows.innerHTML = `<tr><td colspan="3" class="text-center text-gray-500 py-4">No recent activity.</td></tr>`;
            return;
        }
        
        const acts = [];
        s.forEach(c => {
            acts.unshift(c.val()); 
        });

        acts.forEach(a => {
            rows.innerHTML += `
                <tr class="border-b border-gray-100 last:border-0 hover:bg-gray-50 transition">
                    <td class="py-3 text-xs font-mono text-gray-500">${a.time || "Just now"}</td>
                    <td class="py-3 text-sm font-medium text-gray-800">${a.message}</td>
                    <td class="py-3"><span class="h-2 w-2 rounded-full bg-green-500 inline-block mr-2"></span> Done</td>
                </tr>`;
        });
    });
}

// Contact Form (Service Request)
function initContactForm() {
    const form = document.getElementById('requestForm');
    if(!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('submitBtn');
        const spinner = document.getElementById('btnSpinner');
        const msg = document.getElementById('formMessage');
        const btnText = btn ? btn.querySelector('span') : null;

        if(btn && btn.disabled) return;
        
        if(btn) btn.disabled = true;
        if(btnText) btnText.textContent = "Processing...";
        if(spinner) spinner.style.display = 'block';
        if(msg) msg.textContent = "";

        const formData = new FormData(form);

        try {
            // Save to Firebase first
            if(firebase.auth().currentUser) {
                const uid = firebase.auth().currentUser.uid;
                firebase.database().ref(`leads/service_requests/${uid}`).push(Object.fromEntries(formData));
            }

            // Send Email via Python backend
            const response = await fetch(window.location.origin + '/custom', { 
                method: 'POST', 
                body: formData 
            });
            
            if (!response.ok) throw new Error('Network error');
            
            const result = await response.json();
            if(msg) {
                msg.textContent = result.message || "Request Sent Successfully!";
                msg.className = "form-message success";
                msg.style.color = "#10b981"; // Green
            }
            form.reset();

        } catch (error) {
            console.error(error);
            if(msg) {
                msg.textContent = "Error sending request. Please try again.";
                msg.className = "form-message error";
                msg.style.color = "#ef4444"; // Red
            }
            if(btn) btn.disabled = false; 
            if(btnText) btnText.textContent = "Send Request";
        } finally {
            if(spinner) spinner.style.display = 'none';
            if(btn && btn.disabled && btnText) btnText.textContent = "Sent";
        }
    });
}

// Price Estimator Logic
function initPriceEstimator() {
    const els = ['modelType', 'dataSize', 'complexity'];
    
    els.forEach(id => {
        const el = document.getElementById(id);
        if(el) el.addEventListener(el.type === 'range' ? 'input' : 'change', calculateTotal);
    });
    
    document.querySelectorAll('input[name="complexity"]').forEach(r => {
        r.addEventListener('change', calculateTotal);
    });
    
    // Run once on load to establish baseline
    calculateTotal();
}

function calculateTotal() {
    const typeEl = document.getElementById('modelType');
    const sizeEl = document.getElementById('dataSize');
    const compEl = document.querySelector('input[name="complexity"]:checked');
    
    if(!typeEl || !sizeEl || !compEl) return;

    const size = parseInt(sizeEl.value);
    const type = typeEl.value;
    const complexity = compEl.value;

    const sizeDisplay = document.getElementById('sizeDisplay');
    if(sizeDisplay) sizeDisplay.innerText = size.toLocaleString() + " Records";

    // Pricing Model
    const base = { 'tabular': 45000, 'vision': 120000, 'nlp': 95000, 'bio': 180000 };
    let total = base[type] + (size * 0.85);
    if(complexity === 'advanced') total *= 1.6;

    total = Math.ceil(total / 100) * 100;
    
    const priceDisplay = document.getElementById('totalPrice');
    if(priceDisplay) priceDisplay.innerText = "KSH " + total.toLocaleString();
}

/**
 * Global Logout Function
 * 1. Signs out of Firebase
 * 2. Redirects user to the Login page
 */
window.handleLogout = function() {
    if (typeof firebase === 'undefined') return;

    firebase.auth().signOut()
        .then(() => {
            console.log("User signed out.");
            sessionStorage.clear();
            window.location.href = "/login";
        })
        .catch((error) => {
            console.error("Logout Error:", error);
            alert("Error signing out. Please try again.");
        });
};