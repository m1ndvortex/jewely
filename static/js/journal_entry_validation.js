/**
 * Journal Entry Validation
 * 
 * Provides client-side validation for journal entry forms to ensure
 * debits equal credits before submission.
 */

(function() {
    'use strict';
    
    /**
     * Calculate total debits and credits from all line items
     */
    function calculateTotals() {
        let totalDebits = 0;
        let totalCredits = 0;
        
        // Find all debit and credit inputs
        const debitInputs = document.querySelectorAll('.debit-input');
        const creditInputs = document.querySelectorAll('.credit-input');
        
        // Sum up debits
        debitInputs.forEach(input => {
            const value = parseFloat(input.value) || 0;
            totalDebits += value;
        });
        
        // Sum up credits
        creditInputs.forEach(input => {
            const value = parseFloat(input.value) || 0;
            totalCredits += value;
        });
        
        return {
            debits: totalDebits,
            credits: totalCredits,
            difference: Math.abs(totalDebits - totalCredits),
            balanced: Math.abs(totalDebits - totalCredits) < 0.01 // Allow for rounding
        };
    }
    
    /**
     * Update the balance display
     */
    function updateBalanceDisplay() {
        const totals = calculateTotals();
        const balanceDisplay = document.getElementById('balance-display');
        
        if (!balanceDisplay) return;
        
        // Update display values
        const debitTotal = balanceDisplay.querySelector('.debit-total');
        const creditTotal = balanceDisplay.querySelector('.credit-total');
        const differenceDisplay = balanceDisplay.querySelector('.difference');
        const balanceStatus = balanceDisplay.querySelector('.balance-status');
        
        if (debitTotal) {
            debitTotal.textContent = totals.debits.toFixed(2);
        }
        
        if (creditTotal) {
            creditTotal.textContent = totals.credits.toFixed(2);
        }
        
        if (differenceDisplay) {
            differenceDisplay.textContent = totals.difference.toFixed(2);
        }
        
        // Update status indicator
        if (balanceStatus) {
            if (totals.balanced && totals.debits > 0) {
                balanceStatus.textContent = '✓ Balanced';
                balanceStatus.className = 'balance-status text-green-600 font-semibold';
            } else if (totals.debits === 0 && totals.credits === 0) {
                balanceStatus.textContent = '⚠ No entries';
                balanceStatus.className = 'balance-status text-gray-500';
            } else {
                balanceStatus.textContent = '✗ Out of balance';
                balanceStatus.className = 'balance-status text-red-600 font-semibold';
            }
        }
    }
    
    /**
     * Validate form before submission
     */
    function validateForm(event) {
        const totals = calculateTotals();
        
        // Check if balanced
        if (!totals.balanced) {
            event.preventDefault();
            
            const message = `Journal entry is out of balance!\n\n` +
                          `Total Debits: $${totals.debits.toFixed(2)}\n` +
                          `Total Credits: $${totals.credits.toFixed(2)}\n` +
                          `Difference: $${totals.difference.toFixed(2)}\n\n` +
                          `Please ensure debits equal credits before submitting.`;
            
            alert(message);
            return false;
        }
        
        // Check if there are any entries
        if (totals.debits === 0 && totals.credits === 0) {
            event.preventDefault();
            alert('Please add at least one debit and one credit entry.');
            return false;
        }
        
        return true;
    }
    
    /**
     * Validate individual line (ensure only debit OR credit, not both)
     */
    function validateLine(debitInput, creditInput) {
        const debitValue = parseFloat(debitInput.value) || 0;
        const creditValue = parseFloat(creditInput.value) || 0;
        
        // If both have values, clear the one that wasn't just changed
        if (debitValue > 0 && creditValue > 0) {
            // Determine which was changed last by checking focus
            if (document.activeElement === debitInput) {
                creditInput.value = '0.00';
            } else if (document.activeElement === creditInput) {
                debitInput.value = '0.00';
            }
        }
        
        updateBalanceDisplay();
    }
    
    /**
     * Initialize validation when DOM is ready
     */
    function initializeValidation() {
        // Find the journal entry form
        const form = document.querySelector('form[data-journal-entry-form]');
        if (!form) return;
        
        // Add submit validation
        form.addEventListener('submit', validateForm);
        
        // Add real-time validation to all debit/credit inputs
        const debitInputs = document.querySelectorAll('.debit-input');
        const creditInputs = document.querySelectorAll('.credit-input');
        
        // Set up paired validation for each line
        const formRows = document.querySelectorAll('[data-formset-form]');
        formRows.forEach(row => {
            const debitInput = row.querySelector('.debit-input');
            const creditInput = row.querySelector('.credit-input');
            
            if (debitInput && creditInput) {
                debitInput.addEventListener('input', () => {
                    validateLine(debitInput, creditInput);
                });
                
                creditInput.addEventListener('input', () => {
                    validateLine(debitInput, creditInput);
                });
                
                debitInput.addEventListener('blur', () => {
                    // Format to 2 decimal places on blur
                    const value = parseFloat(debitInput.value) || 0;
                    debitInput.value = value.toFixed(2);
                    updateBalanceDisplay();
                });
                
                creditInput.addEventListener('blur', () => {
                    // Format to 2 decimal places on blur
                    const value = parseFloat(creditInput.value) || 0;
                    creditInput.value = value.toFixed(2);
                    updateBalanceDisplay();
                });
            }
        });
        
        // Initial balance calculation
        updateBalanceDisplay();
        
        // Watch for dynamically added forms (if using HTMX or similar)
        const observer = new MutationObserver(() => {
            updateBalanceDisplay();
        });
        
        const formsetContainer = document.querySelector('[data-formset-container]');
        if (formsetContainer) {
            observer.observe(formsetContainer, {
                childList: true,
                subtree: true
            });
        }
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeValidation);
    } else {
        initializeValidation();
    }
    
    // Export functions for external use if needed
    window.journalEntryValidation = {
        calculateTotals: calculateTotals,
        updateBalanceDisplay: updateBalanceDisplay,
        validateForm: validateForm
    };
})();
