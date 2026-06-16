// Global Application State
const state = {
    updates: [],
    filteredUpdates: [],
    activeFilter: 'All',
    searchQuery: '',
    lastUpdated: null,
    selectedUpdateForTweet: null
};

// DOM Elements
const elements = {
    refreshBtn: document.getElementById('refresh-btn'),
    refreshIcon: document.getElementById('refresh-icon'),
    lastUpdatedText: document.getElementById('last-updated-text'),
    searchInput: document.getElementById('search-input'),
    clearSearchBtn: document.getElementById('clear-search-btn'),
    chipsContainer: document.getElementById('chips-container'),
    notesGrid: document.getElementById('notes-grid'),
    loadingState: document.getElementById('loading-state'),
    errorState: document.getElementById('error-state'),
    errorMessage: document.getElementById('error-message'),
    emptyState: document.getElementById('empty-state'),
    retryBtn: document.getElementById('retry-btn'),
    resetFiltersBtn: document.getElementById('reset-filters-btn'),
    
    // Stats elements
    statTotal: document.getElementById('stat-total'),
    statFeatures: document.getElementById('stat-features'),
    statChanges: document.getElementById('stat-changes'),
    statIssues: document.getElementById('stat-issues'),
    statCards: document.querySelectorAll('.stat-card'),
    
    // Modal elements
    tweetModal: document.getElementById('tweet-modal'),
    closeModalBtn: document.getElementById('close-modal-btn'),
    cancelTweetBtn: document.getElementById('cancel-tweet-btn'),
    postTweetBtn: document.getElementById('post-tweet-btn'),
    tweetTextarea: document.getElementById('tweet-textarea'),
    charCounter: document.getElementById('char-counter'),
    charProgress: document.getElementById('char-progress'),
    charProgressContainer: document.querySelector('.character-progress-container'),
    modalUpdatePreview: document.getElementById('modal-update-preview'),
    
    // Toast Container
    toastContainer: document.getElementById('toast-container')
};

// Constants
const TWITTER_CHAR_LIMIT = 280;

// Initialize the Application
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    // Fetch initial data
    fetchReleaseNotes();
    
    // Bind Event Listeners
    elements.refreshBtn.addEventListener('click', () => fetchReleaseNotes(true));
    elements.retryBtn.addEventListener('click', () => fetchReleaseNotes(true));
    elements.resetFiltersBtn.addEventListener('click', resetFilters);
    
    // Search input handlers
    elements.searchInput.addEventListener('input', handleSearch);
    elements.clearSearchBtn.addEventListener('click', clearSearch);
    
    // Filter chip handlers
    setupFilterChips();
    
    // Stats card click handlers (which filter the content)
    elements.statCards.forEach(card => {
        card.addEventListener('click', () => {
            const filterType = card.dataset.filter;
            setActiveFilter(filterType);
        });
    });
    
    // Modal handlers
    elements.closeModalBtn.addEventListener('click', closeTweetModal);
    elements.cancelTweetBtn.addEventListener('click', closeTweetModal);
    elements.tweetTextarea.addEventListener('input', updateCharCount);
    elements.postTweetBtn.addEventListener('click', postTweet);
    
    // Close modal on outside click
    elements.tweetModal.addEventListener('click', (e) => {
        if (e.target === elements.tweetModal) {
            closeTweetModal();
        }
    });
}

// Fetch Release Notes from Flask API
async function fetchReleaseNotes(forceRefresh = false) {
    showLoading();
    
    let url = '/api/release-notes';
    if (forceRefresh) {
        url += '?refresh=true';
        elements.refreshIcon.classList.add('spinning');
        elements.refreshBtn.disabled = true;
    }
    
    try {
        const response = await fetch(url);
        const result = await response.json();
        
        if (result.status === 'success' || result.status === 'warning') {
            state.updates = result.data;
            state.lastUpdated = new Date(result.last_updated * 1000);
            
            // Render UI
            updateLastUpdatedDisplay();
            updateStats();
            applySearchAndFilter();
            
            if (result.status === 'warning') {
                showToast(result.message, 'warning');
            } else if (forceRefresh) {
                showToast('Release notes successfully refreshed!', 'success');
            }
        } else {
            throw new Error(result.message || 'Unknown server error');
        }
    } catch (error) {
        console.error('Error fetching release notes:', error);
        showError(error.message);
        showToast('Error refreshing release notes.', 'error');
    } finally {
        elements.refreshIcon.classList.remove('spinning');
        elements.refreshBtn.disabled = false;
    }
}

// UI State Toggles
function showLoading() {
    elements.loadingState.style.display = 'flex';
    elements.notesGrid.style.display = 'none';
    elements.errorState.style.display = 'none';
    elements.emptyState.style.display = 'none';
}

function showError(message) {
    elements.errorMessage.textContent = message || 'Could not fetch updates at this time.';
    elements.loadingState.style.display = 'none';
    elements.notesGrid.style.display = 'none';
    elements.errorState.style.display = 'flex';
    elements.emptyState.style.display = 'none';
}

function showContent() {
    elements.loadingState.style.display = 'none';
    elements.notesGrid.style.display = 'grid';
    elements.errorState.style.display = 'none';
    elements.emptyState.style.display = 'none';
}

function showEmpty() {
    elements.loadingState.style.display = 'none';
    elements.notesGrid.style.display = 'none';
    elements.errorState.style.display = 'none';
    elements.emptyState.style.display = 'flex';
}

// Update the Last Updated Text
function updateLastUpdatedDisplay() {
    if (!state.lastUpdated) {
        elements.lastUpdatedText.textContent = '';
        return;
    }
    
    const options = { hour: '2-digit', minute: '2-digit', second: '2-digit' };
    const timeStr = state.lastUpdated.toLocaleTimeString(undefined, options);
    elements.lastUpdatedText.textContent = `Last synced: ${timeStr}`;
}

// Compute Statistics Dashboard
function updateStats() {
    const total = state.updates.length;
    const features = state.updates.filter(u => u.type.toLowerCase() === 'feature').length;
    const changes = state.updates.filter(u => u.type.toLowerCase() === 'change').length;
    const issues = state.updates.filter(u => u.type.toLowerCase() === 'issue').length;
    
    // Animate stats counting
    animateCounter(elements.statTotal, total);
    animateCounter(elements.statFeatures, features);
    animateCounter(elements.statChanges, changes);
    animateCounter(elements.statIssues, issues);
}

function animateCounter(element, targetValue) {
    let currentValue = parseInt(element.textContent) || 0;
    if (currentValue === targetValue) return;
    
    const duration = 800; // ms
    const startTime = performance.now();
    
    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing out function
        const ease = 1 - Math.pow(1 - progress, 3);
        const value = Math.floor(currentValue + (targetValue - currentValue) * ease);
        
        element.textContent = value;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = targetValue;
        }
    }
    requestAnimationFrame(update);
}

// Filter Chip setups
function setupFilterChips() {
    const chips = elements.chipsContainer.querySelectorAll('.chip');
    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const type = chip.dataset.type;
            setActiveFilter(type);
        });
    });
}

function setActiveFilter(type) {
    state.activeFilter = type;
    
    // Update chip active classes
    const chips = elements.chipsContainer.querySelectorAll('.chip');
    chips.forEach(chip => {
        if (chip.dataset.type === type) {
            chip.classList.add('active');
        } else {
            chip.classList.remove('active');
        }
    });
    
    applySearchAndFilter();
}

// Search Handler
function handleSearch(e) {
    state.searchQuery = e.target.value.toLowerCase().strip ? e.target.value.toLowerCase().trim() : e.target.value.toLowerCase();
    
    if (state.searchQuery.length > 0) {
        elements.clearSearchBtn.style.display = 'flex';
    } else {
        elements.clearSearchBtn.style.display = 'none';
    }
    
    applySearchAndFilter();
}

function clearSearch() {
    elements.searchInput.value = '';
    state.searchQuery = '';
    elements.clearSearchBtn.style.display = 'none';
    applySearchAndFilter();
    elements.searchInput.focus();
}

function resetFilters() {
    elements.searchInput.value = '';
    state.searchQuery = '';
    elements.clearSearchBtn.style.display = 'none';
    setActiveFilter('All');
}

// Filtering and Searching logic
function applySearchAndFilter() {
    state.filteredUpdates = state.updates.filter(update => {
        // 1. Apply Tag filter
        if (state.activeFilter !== 'All') {
            if (update.type.toLowerCase() !== state.activeFilter.toLowerCase()) {
                return false;
            }
        }
        
        // 2. Apply Search Query
        if (state.searchQuery) {
            const matchesText = update.full_text.toLowerCase().includes(state.searchQuery);
            const matchesType = update.type.toLowerCase().includes(state.searchQuery);
            const matchesDate = update.date.toLowerCase().includes(state.searchQuery);
            return matchesText || matchesType || matchesDate;
        }
        
        return true;
    });
    
    renderNotesGrid();
}

// Render the grid of cards
function renderNotesGrid() {
    if (state.filteredUpdates.length === 0) {
        showEmpty();
        return;
    }
    
    showContent();
    elements.notesGrid.innerHTML = '';
    
    state.filteredUpdates.forEach(update => {
        const card = createNoteCard(update);
        elements.notesGrid.appendChild(card);
    });
}

function createNoteCard(update) {
    const card = document.createElement('div');
    card.className = 'note-card';
    
    // Set custom accent color border on left based on update type
    let typeColor = 'var(--color-default)';
    const typeLower = update.type.toLowerCase();
    if (typeLower === 'feature') typeColor = 'var(--color-feature)';
    else if (typeLower === 'change') typeColor = 'var(--color-change)';
    else if (typeLower === 'issue') typeColor = 'var(--color-issue)';
    else if (typeLower === 'deprecation') typeColor = 'var(--color-deprecation)';
    
    card.style.setProperty('--type-color', typeColor);
    
    // Prepare badge class
    let badgeClass = 'default';
    if (['feature', 'change', 'issue', 'deprecation'].includes(typeLower)) {
        badgeClass = typeLower;
    }
    
    card.innerHTML = `
        <div class="card-header-meta">
            <div class="badge-and-date">
                <span class="badge ${badgeClass}">${update.type}</span>
                <span class="note-date">${update.date}</span>
            </div>
            <a href="${update.link}" target="_blank" class="external-source-link" title="Open source documentation">
                <span>Docs</span> <i class="fa-solid fa-arrow-up-right-from-square"></i>
            </a>
        </div>
        <div class="note-content">
            ${highlightKeyword(update.content_html, state.searchQuery)}
        </div>
        <div class="card-actions">
            <button class="action-btn copy-btn" data-id="${update.id}">
                <i class="fa-regular fa-copy"></i> Copy Note
            </button>
            <button class="action-btn tweet-btn" data-id="${update.id}">
                <i class="fa-brands fa-x-twitter"></i> Tweet Note
            </button>
        </div>
    `;
    
    // Bind click events directly
    card.querySelector('.copy-btn').addEventListener('click', () => copyToClipboard(update));
    card.querySelector('.tweet-btn').addEventListener('click', () => openTweetModal(update));
    
    return card;
}

// Highlight searched keywords
function highlightKeyword(html, query) {
    if (!query) return html;
    
    // Avoid breaking HTML tags by doing smart regex highlighting outside tags
    // This splits the HTML string by tags, highlights the text parts, and joins back.
    const parts = html.split(/(<[^>]+>)/g);
    const highlightedParts = parts.map(part => {
        if (part.startsWith('<')) return part; // Keep tag intact
        
        // Escape regex special chars
        const escapedQuery = query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        const regex = new RegExp(`(${escapedQuery})`, 'gi');
        return part.replace(regex, '<mark style="background-color: rgba(99, 102, 241, 0.4); color: white; padding: 0.1rem 0.2rem; border-radius: 3px;">$1</mark>');
    });
    
    return highlightedParts.join('');
}

// Copy release note text to clipboard
function copyToClipboard(update) {
    const formattedText = `BigQuery Update [${update.date}] - ${update.type}\n\n${update.full_text}\n\nRead more: ${update.link}`;
    
    navigator.clipboard.writeText(formattedText)
        .then(() => {
            showToast('Release note copied to clipboard!', 'success');
        })
        .catch(err => {
            console.error('Failed to copy text: ', err);
            showToast('Failed to copy to clipboard.', 'error');
        });
}

// Tweet Customizer Modal Handlers
function openTweetModal(update) {
    state.selectedUpdateForTweet = update;
    elements.tweetModal.classList.add('active');
    
    // Construct default Tweet draft
    // Structure: BigQuery [Type] ([Date]): [Snippet] #BigQuery #GCP [Link]
    const header = `BigQuery ${update.type} (${update.date}): `;
    const tags = ` #BigQuery #GCP`;
    const link = `\nSource: ${update.link}`;
    
    // Calculate space left for the main description snippet
    // Note: Twitter counts any URL as 23 characters regardless of length.
    const urlLengthForTwitter = 23;
    const textUsedByMetadata = header.length + tags.length + urlLengthForTwitter + 10; // offset buffer
    const descriptionCharLimit = TWITTER_CHAR_LIMIT - textUsedByMetadata;
    
    let description = update.full_text;
    if (description.length > descriptionCharLimit) {
        description = description.slice(0, descriptionCharLimit - 3) + '...';
    }
    
    const draftText = `${header}"${description}"${tags}${link}`;
    
    elements.tweetTextarea.value = draftText;
    
    // Render mini preview card in modal
    let badgeClass = 'default';
    if (['feature', 'change', 'issue', 'deprecation'].includes(update.type.toLowerCase())) {
        badgeClass = update.type.toLowerCase();
    }
    
    elements.modalUpdatePreview.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom: 0.25rem;">
            <span class="badge ${badgeClass}" style="font-size:0.65rem;">${update.type}</span>
            <span style="font-size:0.75rem;">${update.date}</span>
        </div>
        <p style="font-size: 0.75rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${update.full_text}</p>
    `;
    
    updateCharCount();
    elements.tweetTextarea.focus();
    
    // Put cursor at end of textarea
    elements.tweetTextarea.setSelectionRange(draftText.length, draftText.length);
}

function closeTweetModal() {
    elements.tweetModal.classList.remove('active');
    state.selectedUpdateForTweet = null;
}

function updateCharCount() {
    const text = elements.tweetTextarea.value;
    
    // Smart character count for Twitter: URLs are counted as 23 characters
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const urls = text.match(urlRegex) || [];
    
    let twitterCount = text.replace(urlRegex, '').length;
    twitterCount += (urls.length * 23);
    
    elements.charCounter.textContent = `${twitterCount} / ${TWITTER_CHAR_LIMIT}`;
    
    // Calculate percentage for progress circle/bar
    const percent = Math.min((twitterCount / TWITTER_CHAR_LIMIT) * 100, 100);
    elements.charProgress.style.width = `${percent}%`;
    
    // Visual indicators for warnings/errors
    if (twitterCount > TWITTER_CHAR_LIMIT) {
        elements.charProgressContainer.className = 'character-progress-container error';
        elements.charProgress.className = 'progress-bar-fill error';
        elements.postTweetBtn.disabled = true;
    } else if (twitterCount > TWITTER_CHAR_LIMIT - 30) {
        elements.charProgressContainer.className = 'character-progress-container warning';
        elements.charProgress.className = 'progress-bar-fill warning';
        elements.postTweetBtn.disabled = false;
    } else {
        elements.charProgressContainer.className = 'character-progress-container';
        elements.charProgress.className = 'progress-bar-fill';
        elements.postTweetBtn.disabled = false;
    }
}

function postTweet() {
    const text = elements.tweetTextarea.value;
    
    // Construct Web Intent URL
    const intentUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`;
    
    // Open in a new window/tab
    window.open(intentUrl, '_blank', 'width=550,height=420,toolbar=0,status=0');
    
    closeTweetModal();
    showToast('Redirected to Twitter to complete post!', 'success');
}

// Show feedback toasts
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'fa-circle-info';
    if (type === 'success') icon = 'fa-circle-check';
    else if (type === 'error') icon = 'fa-triangle-exclamation';
    else if (type === 'warning') icon = 'fa-triangle-exclamation';
    
    toast.innerHTML = `
        <i class="fa-solid ${icon} toast-icon ${type}"></i>
        <span>${message}</span>
    `;
    
    elements.toastContainer.appendChild(toast);
    
    // Slide out and remove after 3.5s
    setTimeout(() => {
        toast.style.animation = 'toast-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) reverse forwards';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3500);
}
