"""Export the contract without opening connections or requiring deployment secrets."""

import json
import sys

from pulse.main import create_app
from pulse.platform.config import Settings


def main() -> None:
    app = create_app(
        Settings(
            database_url="postgresql+psycopg://unused:unused@localhost/unused",
            redis_url="redis://localhost:6379/0",
        )
    )
    print(json.dumps(app.openapi(), indent=2, sort_keys=True), file=sys.stdout)


if __name__ == "__main__":
    main()
