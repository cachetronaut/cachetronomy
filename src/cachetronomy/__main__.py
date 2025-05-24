"""
Entrypoint for cachetronomy CLI.

Allows running the package as a script via `python -m cachetronomy`,
invoking the CLI’s main function.
"""

from cachetronomy.cli import main

if __name__ == '__main__':
    main()