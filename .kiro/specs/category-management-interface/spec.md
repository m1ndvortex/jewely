# Category Management Interface Redesign

## Overview
Complete UI/UX redesign of the category management page at `/inventory/categories/` to match the provided design mockup. This is a **frontend-only change** - all backend models, views, and functionality remain unchanged.

## Design Requirements

### Layout Structure
1. **Two-column layout**:
   - Left sidebar (fixed width ~280px): Category navigation
   - Main content area (flexible): Category details and subcategories

2. **Left Sidebar Components**:
   - Header: "Categories" title with subtitle
   - Collapse/expand button (top right)
   - Search input field
   - "MAIN CATEGORIES" section label
   - List of main categories with icons and expand arrows
   - Active category highlighted

3. **Main Content Components**:
   - Category header with name and "Active" badge
   - Stats: Total Products count, Subcategories count
   - "Add Subcategory" button (top right)
   - Category Details card with:
     - Name, Status badge, Items count, Icon display
     - Description text
     - Action buttons: Edit Category, View All Products, Delete Category
   - Subcategories table with columns:
     - Checkbox (for bulk actions)
     - Icon
     - Name
     - Products count
     - Subcats count
     - Status badge
     - Actions (view, edit, delete icons)

### Visual Design
- Clean, modern interface with card-based design
- Consistent spacing and typography
- Icon usage for visual hierarchy
- Color scheme:
  - Active status: Green badge
  - Primary actions: Dark blue/slate buttons
  - Destructive actions: Light red/pink
  - Neutral: Gray tones
- Responsive design principles

## Technical Implementation

### Files to Modify
1. `templates/inventory/category_list.html` - Complete redesign
2. No backend changes required

### Backend Context (No Changes)
- View: `apps/inventory/web_views.py::category_list_view`
- Model: `apps/inventory/models.py::ProductCategory`
- All existing fields and relationships remain unchanged

### Key Features to Preserve
- Tenant isolation
- Search functionality
- Category hierarchy (parent/subcategories)
- All CRUD operations
- Statistics display
- Active/inactive status

## Implementation Notes
- Use Tailwind CSS (already available in base template)
- Maintain dark mode support
- Keep i18n/translation support
- Preserve all existing URLs and view logic
- No database migrations needed
