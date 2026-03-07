# {{project_title}}

A SwX Framework application.

## Quick Start

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Set up database
swx db migrate

# Run development server
swx serve
```

## CLI Commands

```bash
swx --help              # Show all commands
swx serve               # Start development server
swx setup               # Interactive setup wizard
swx doctor              # System diagnostics
swx db migrate          # Run migrations
swx db revision -m "message"  # Create new migration
swx make:resource <name>      # Generate CRUD scaffold
```

## Project Structure

```
{{project_name}}/
├── swx_app/              # Application code
│   ├── models/           # Database models
│   ├── routes/           # API routes
│   ├── controllers/      # Business logic
│   ├── services/         # Domain services
│   ├── repositories/     # Data access
│   ├── providers/        # Service providers
│   ├── listeners/        # Event listeners
│   ├── middleware/       # Custom middleware
│   └── plugins/          # Plugins
├── migrations/           # Database migrations
├── tests/                # Test files
├── .env                  # Environment configuration
└── requirements.txt      # Dependencies
```

## Documentation

- [SwX Documentation](https://swx-framework.readthedocs.io)
- [Getting Started](https://swx-framework.readthedocs.io/en/latest/getting-started/)
- [API Reference](https://swx-framework.readthedocs.io/en/latest/api/)

## License

MIT