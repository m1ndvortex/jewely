# Screen Reader Testing Guide

## Overview

This guide provides comprehensive instructions for testing the Jewelry Management SaaS Platform with assistive technologies, specifically screen readers. This testing is required per **Requirement 29** (WCAG 2.1 Level AA Compliance) and **Task 30.4**.

## Purpose

Screen reader testing ensures that users with visual impairments can effectively use all features of the application. While automated tests can verify technical compliance (ARIA attributes, semantic HTML, etc.), manual testing with actual screen readers is essential to verify the user experience.

## Screen Readers to Test

Per Requirement 29, the application must be tested with:

1. **NVDA (NonVisual Desktop Access)** - Windows, Free
2. **JAWS (Job Access With Speech)** - Windows, Commercial
3. **VoiceOver** - macOS/iOS, Built-in

## Testing Environment Setup

### NVDA Setup (Windows)

1. **Download and Install:**
   - Visit: https://www.nvaccess.org/download/
   - Download the latest stable version
   - Install with default settings

2. **Basic Controls:**
   - Start NVDA: `Ctrl + Alt + N`
   - Stop NVDA: `Insert + Q`
   - Toggle speech: `Insert + S`
   - Read current line: `Insert + Up Arrow`
   - Read from cursor: `Insert + Down Arrow`
   - Navigate by heading: `H` (next), `Shift + H` (previous)
   - Navigate by link: `K` (next), `Shift + K` (previous)
   - Navigate by button: `B` (next), `Shift + B` (previous)
   - Navigate by form field: `F` (next), `Shift + F` (previous)
   - Navigate by landmark: `D` (next), `Shift + D` (previous)

3. **Browser Compatibility:**
   - Use Firefox or Chrome (best NVDA support)
   - Ensure browser is up to date

### JAWS Setup (Windows)

1. **Download and Install:**
   - Visit: https://www.freedomscientific.com/products/software/jaws/
   - Download trial or licensed version
   - Install with default settings

2. **Basic Controls:**
   - Start JAWS: Automatically starts with Windows
   - Stop JAWS: `Insert + F4`
   - Toggle speech: `Insert + Space, then S`
   - Read current line: `Insert + Up Arrow`
   - Read from cursor: `Insert + Page Down`
   - Navigate by heading: `H` (next), `Shift + H` (previous)
   - Navigate by link: `Tab` or `Insert + F7` (links list)
   - Navigate by button: `B` (next), `Shift + B` (previous)
   - Navigate by form field: `F` (next), `Shift + F` (previous)
   - Navigate by landmark: `R` (next), `Shift + R` (previous)

3. **Browser Compatibility:**
   - Use Chrome, Firefox, or Edge
   - JAWS works best with Chrome

### VoiceOver Setup (macOS)

1. **Enable VoiceOver:**
   - Press `Cmd + F5` to toggle VoiceOver
   - Or: System Preferences > Accessibility > VoiceOver > Enable

2. **Basic Controls:**
   - VoiceOver modifier key: `Control + Option` (VO)
   - Start/Stop: `Cmd + F5`
   - Read from cursor: `VO + A`
   - Navigate by heading: `VO + Cmd + H`
   - Navigate by link: `VO + Cmd + L`
   - Navigate by form control: `VO + Cmd + J`
   - Navigate by landmark: `VO + U` (Web Rotor)
   - Interact with element: `VO + Space`

3. **Browser Compatibility:**
   - Use Safari (best VoiceOver support)
   - Chrome and Firefox also work

## Testing Checklist

### 1. Page Structure and Navigation

#### Test: Skip Navigation Links
- [ ] **NVDA/JAWS:** Press `Tab` immediately after page load
- [ ] **VoiceOver:** Press `VO + Right Arrow` after page load
- [ ] **Expected:** First focusable element should be "Skip to main content" link
- [ ] **Action:** Activate the skip link
- [ ] **Expected:** Focus should move to main content area

#### Test: Landmark Navigation
- [ ] **NVDA:** Press `D` to navigate between landmarks
- [ ] **JAWS:** Press `R` to navigate between landmarks
- [ ] **VoiceOver:** Press `VO + U`, select Landmarks
- [ ] **Expected:** Should announce landmarks: Navigation, Main, etc.
- [ ] **Expected:** Each landmark should have a descriptive label

#### Test: Heading Structure
- [ ] **NVDA/JAWS:** Press `H` to navigate between headings
- [ ] **VoiceOver:** Press `VO + Cmd + H` to navigate headings
- [ ] **Expected:** Headings should be announced with level (e.g., "Heading level 1, Dashboard")
- [ ] **Expected:** Heading hierarchy should be logical (h1 → h2 → h3, no skipping)
- [ ] **Expected:** Page should have exactly one h1

### 2. Forms and Input Fields

#### Test: Login Form
- [ ] Navigate to login page
- [ ] **Tab through form fields**
- [ ] **Expected:** Each field should announce its label and type
- [ ] **Expected:** Required fields should be announced as "required"
- [ ] **Expected:** Password field should be announced as "password, protected"

#### Test: Form Validation
- [ ] Submit login form with empty fields
- [ ] **Expected:** Error messages should be announced immediately
- [ ] **Expected:** Focus should move to first error field
- [ ] **Expected:** Each field should announce its error message
- [ ] **Expected:** Error messages should be clear and actionable

#### Test: Form Instructions
- [ ] Navigate to complex forms (e.g., inventory item creation)
- [ ] **Expected:** Instructions should be announced before or with the field
- [ ] **Expected:** Help text should be associated with fields (aria-describedby)

### 3. Interactive Elements

#### Test: Buttons
- [ ] Navigate to dashboard
- [ ] **Tab to buttons**
- [ ] **Expected:** Each button should announce its purpose
- [ ] **Expected:** Button state should be announced (e.g., "expanded", "collapsed")
- [ ] **Expected:** Icon-only buttons should have descriptive labels

#### Test: Links
- [ ] Navigate through page content
- [ ] **NVDA/JAWS:** Press `K` to navigate links
- [ ] **VoiceOver:** Press `VO + Cmd + L` to navigate links
- [ ] **Expected:** Link text should be descriptive (not "click here")
- [ ] **Expected:** External links should announce "opens in new window"
- [ ] **Expected:** Current page link should be announced as "current page"

#### Test: Dropdown Menus
- [ ] Navigate to navigation menu
- [ ] **Activate dropdown menu**
- [ ] **Expected:** Menu should announce "expanded" when opened
- [ ] **Expected:** Menu items should be navigable with arrow keys
- [ ] **Expected:** Escape key should close menu

### 4. Dynamic Content

#### Test: Notifications
- [ ] Trigger a notification (e.g., save a form)
- [ ] **Expected:** Notification should be announced immediately
- [ ] **Expected:** Notification should use aria-live region
- [ ] **Expected:** User should be able to dismiss notification

#### Test: Loading States
- [ ] Trigger a loading state (e.g., submit form)
- [ ] **Expected:** Loading state should be announced
- [ ] **Expected:** User should know when loading is complete

#### Test: Modal Dialogs
- [ ] Open a modal dialog
- [ ] **Expected:** Focus should move to modal
- [ ] **Expected:** Modal title should be announced
- [ ] **Expected:** Focus should be trapped within modal
- [ ] **Expected:** Escape key should close modal
- [ ] **Expected:** Focus should return to trigger element when closed

### 5. Data Tables

#### Test: Inventory Table
- [ ] Navigate to inventory list
- [ ] **NVDA/JAWS:** Press `T` to navigate to table
- [ ] **VoiceOver:** Press `VO + U`, select Tables
- [ ] **Expected:** Table should announce number of rows and columns
- [ ] **Expected:** Column headers should be announced with each cell
- [ ] **Expected:** Row headers should be announced (if applicable)

#### Test: Table Navigation
- [ ] Navigate within table
- [ ] **NVDA/JAWS:** Use `Ctrl + Alt + Arrow Keys` to navigate cells
- [ ] **VoiceOver:** Use `VO + Arrow Keys` to navigate cells
- [ ] **Expected:** Each cell should announce its content and position

### 6. Images and Media

#### Test: Images
- [ ] Navigate through pages with images
- [ ] **Expected:** All images should have alt text
- [ ] **Expected:** Decorative images should be ignored (alt="" or role="presentation")
- [ ] **Expected:** Complex images should have detailed descriptions

#### Test: Icons
- [ ] Navigate to pages with icons
- [ ] **Expected:** Functional icons should have labels
- [ ] **Expected:** Decorative icons should be hidden from screen readers

### 7. Keyboard Navigation

#### Test: Tab Order
- [ ] Navigate through entire page using Tab key
- [ ] **Expected:** Tab order should be logical (left to right, top to bottom)
- [ ] **Expected:** All interactive elements should be reachable
- [ ] **Expected:** No keyboard traps (can always tab away)

#### Test: Focus Indicators
- [ ] Navigate using keyboard
- [ ] **Expected:** Focus indicator should be clearly visible
- [ ] **Expected:** Focus indicator should have sufficient contrast
- [ ] **Expected:** Focus indicator should not be hidden by CSS

#### Test: Keyboard Shortcuts
- [ ] Test application keyboard shortcuts
- [ ] **Expected:** Shortcuts should be documented
- [ ] **Expected:** Shortcuts should not conflict with screen reader shortcuts
- [ ] **Expected:** Shortcuts should be announced or discoverable

### 8. Multi-Language Support

#### Test: Persian (RTL) Mode
- [ ] Switch language to Persian
- [ ] **Expected:** Screen reader should announce content in Persian
- [ ] **Expected:** Navigation should work in RTL layout
- [ ] **Expected:** All functionality should work in RTL mode

### 9. POS System

#### Test: POS Interface
- [ ] Navigate to POS interface
- [ ] **Expected:** Product search should be accessible
- [ ] **Expected:** Cart items should be announced
- [ ] **Expected:** Payment method selection should be accessible
- [ ] **Expected:** Receipt generation should be announced

#### Test: Barcode Scanner
- [ ] Test barcode scanner integration
- [ ] **Expected:** Scanner input should be announced
- [ ] **Expected:** Product added to cart should be announced

### 10. Reporting and Analytics

#### Test: Charts and Graphs
- [ ] Navigate to dashboard with charts
- [ ] **Expected:** Charts should have text alternatives
- [ ] **Expected:** Data should be available in table format
- [ ] **Expected:** Key insights should be announced

## Common Issues and Solutions

### Issue: Element Not Announced
**Possible Causes:**
- Missing label or aria-label
- Element hidden with display:none or visibility:hidden
- Element has aria-hidden="true"

**Solution:**
- Add proper label or aria-label
- Use sr-only class for visually hidden labels
- Remove aria-hidden if element should be accessible

### Issue: Incorrect Announcement
**Possible Causes:**
- Wrong ARIA role
- Incorrect aria-labelledby reference
- Conflicting labels

**Solution:**
- Use correct semantic HTML or ARIA role
- Verify aria-labelledby points to correct element
- Remove duplicate or conflicting labels

### Issue: Focus Not Visible
**Possible Causes:**
- CSS removes outline
- Focus indicator has insufficient contrast
- Focus indicator is hidden behind other elements

**Solution:**
- Add visible focus styles with :focus-visible
- Ensure 3:1 contrast ratio for focus indicators
- Adjust z-index to keep focus visible

### Issue: Keyboard Trap
**Possible Causes:**
- Modal doesn't trap focus properly
- Custom widget doesn't handle keyboard navigation
- Tab order is broken

**Solution:**
- Implement proper focus management in modals
- Add keyboard event handlers for custom widgets
- Fix tab order with tabindex if necessary

## Testing Report Template

### Test Session Information
- **Date:** [Date]
- **Tester:** [Name]
- **Screen Reader:** [NVDA/JAWS/VoiceOver]
- **Version:** [Version number]
- **Browser:** [Browser and version]
- **Operating System:** [OS and version]

### Test Results

#### Page/Feature: [Name]
- **Status:** [Pass/Fail/Partial]
- **Issues Found:**
  1. [Description of issue]
  2. [Description of issue]
- **Severity:** [Critical/High/Medium/Low]
- **Steps to Reproduce:**
  1. [Step 1]
  2. [Step 2]
- **Expected Behavior:** [What should happen]
- **Actual Behavior:** [What actually happened]
- **Screenshots/Videos:** [If applicable]

### Summary
- **Total Tests:** [Number]
- **Passed:** [Number]
- **Failed:** [Number]
- **Critical Issues:** [Number]
- **Recommendations:** [List of recommendations]

## Best Practices for Developers

1. **Use Semantic HTML:** Use proper HTML elements (button, nav, main, etc.) instead of divs with roles
2. **Provide Text Alternatives:** All non-text content should have text alternatives
3. **Ensure Keyboard Accessibility:** All functionality should be available via keyboard
4. **Use ARIA Appropriately:** Use ARIA to enhance, not replace, semantic HTML
5. **Test Early and Often:** Test with screen readers during development, not just at the end
6. **Include Users with Disabilities:** Involve users with disabilities in testing when possible

## Resources

### Screen Reader Documentation
- **NVDA:** https://www.nvaccess.org/documentation/
- **JAWS:** https://www.freedomscientific.com/training/jaws/
- **VoiceOver:** https://support.apple.com/guide/voiceover/welcome/mac

### WCAG Guidelines
- **WCAG 2.1:** https://www.w3.org/WAI/WCAG21/quickref/
- **ARIA Authoring Practices:** https://www.w3.org/WAI/ARIA/apg/

### Testing Tools
- **axe DevTools:** Browser extension for automated accessibility testing
- **WAVE:** Web accessibility evaluation tool
- **Lighthouse:** Built into Chrome DevTools

## Automated Testing

While manual testing is essential, automated tests complement manual testing:

```bash
# Run automated accessibility tests
docker compose exec web pytest apps/core/tests/test_assistive_technology.py -v

# Run all accessibility tests
docker compose exec web pytest apps/core/test_accessibility.py apps/core/tests/test_assistive_technology.py -v
```

## Continuous Monitoring

1. **Include in CI/CD:** Run automated accessibility tests in CI/CD pipeline
2. **Regular Manual Testing:** Schedule quarterly manual screen reader testing
3. **User Feedback:** Collect feedback from users with disabilities
4. **Stay Updated:** Keep up with WCAG updates and screen reader changes

## Conclusion

Screen reader testing is an ongoing process. This guide should be updated as new features are added and as screen reader technology evolves. The goal is to ensure that all users, regardless of ability, can effectively use the Jewelry Management SaaS Platform.

---

**Document Version:** 1.0  
**Last Updated:** 2024-11-07  
**Next Review:** 2025-02-07
