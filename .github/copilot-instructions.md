# MTG Shop Management System - AI Agent Instructions

## Architecture Overview
This is a Flask-based web application for managing a Magic: The Gathering card shop. The system handles inventory, sales, user management, and financial tracking with a role-based permission system.

**Core Components:**
- **User Management**: Admin/vendeur roles with granular permissions (JSON-stored in database)
- **Inventory**: Products with boutique stock, depot stock, and "en route" quantities
- **Sales System**: Invoices, payments, credit tracking, and delivery management
- **Financial**: Cash register, bank account, and expense tracking (ordinary/recurring)
- **Frontend**: AJAX-heavy interface using jQuery, Bootstrap, and custom JavaScript classes

## Key Files & Structure
- `run.py`: Application entry point with production keep-alive service
- `app/__init__.py`: Flask app factory with SQLite configuration
- `app/models.py`: SQLAlchemy models (User, Produits, Factures, Ventes, etc.)
- `app/routes.py`: All endpoints with permission decorators
- `app/templates/`: Jinja2 templates with French UI text
- `app/static/js/ventes_ajax.js`: Class-based cart management (PanierManager)
- `create_db.py`: Database initialization with default admin user

## Development Workflow
```bash
# Initialize database
python create_db.py

# Run locally
python run.py

# Production deployment uses Gunicorn + keep-alive service
```

## Code Patterns & Conventions

### Authentication & Permissions
- Use `@login_required` and `@permission_required('permission_name')` decorators
- Check permissions with `current_user.has_permission('permission')`
- Admin role bypasses all permission checks
- Permissions stored as JSON array in User model

### Database Operations
- Use SQLAlchemy ORM with relationships/backrefs
- Foreign keys follow `table_id` naming (e.g., `produit_id`, `facture_id`)
- Date fields default to `datetime.utcnow`
- Enum fields for status/type constraints

### AJAX API Pattern
```javascript
// Frontend AJAX calls follow this pattern
fetch('/api/endpoint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        // Handle success
        this.afficherNotification('Success message', 'success');
    } else {
        // Handle error
        this.afficherNotification(data.message, 'error');
    }
});
```

### French Language Convention
- All user-facing text, comments, and variable names are in French
- Database field names: `nom_client`, `montant_total`, `date_facture`
- UI strings: "Produit ajouté au panier", "Connexion réussie"

### JavaScript Classes
- Complex UI components use ES6 classes (e.g., `PanierManager`)
- Methods follow camelCase: `mettreAJourInterface()`, `chargerPanier()`
- Error handling with try/catch and user notifications

### File Uploads
- Use `werkzeug.utils.secure_filename()` for uploaded files
- Store in `app.config['UPLOAD_FOLDER']` with UUID prefixes
- Clean up old files when replacing user photos

## Common Integration Points
- **Bootstrap 5**: Responsive UI with local CSS files
- **Font Awesome**: Icons throughout the interface
- **jQuery**: DOM manipulation and AJAX calls
- **Pillow**: Image processing for uploads
- **SQLite**: File-based database in `db/gestion_stock.sqlite`

## Deployment Configuration
- **Render**: Uses `render.yaml` for Python service deployment
- **Docker**: Available with Gunicorn on port 8000
- **Keep-alive**: Background service pings app every 4 minutes in production

## Database Schema Highlights
- **Stock tracking**: `quantite` (boutique) + `quantite_depot` + `en_route`
- **Sales flow**: Facture → Ventes → Benefices calculation
- **Credit system**: `montant_credit` tracking with payment history
- **Delivery**: Depot-based with status tracking (`en_attente`, `prepare`, `livree`)

When modifying code, maintain French language consistency and ensure permission checks are properly implemented for new features.</content>
<parameter name="filePath">d:\Nouveau dossier\MES PROJET\mtgshop\.github\copilot-instructions.md