# Configuration contract

## Source precedence

Sources override one another in this order:

1. Earlier TOML files
2. Later TOML files
3. Earlier dotenv files
4. Later dotenv files
5. Process environment
6. Explicit overrides, including supplied CLI flags

An empty process or override value still replaces a file value and then fails required-value validation.

## Validation

- Every field is required. Empty and whitespace-only values are missing.
- Alternate environment names for one field are mutually exclusive.
- Parsers receive one stripped string and run once per load.
- A parser's `ValueError` marks the field invalid. Other exceptions propagate as programming errors.
- Validation errors identify fields, names, sources, and reasons without including input values or parser exception text.
- Loading does not modify `os.environ`. Loaded configuration attributes are read-only.
