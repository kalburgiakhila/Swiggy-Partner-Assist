from __future__ import annotations

import click
from flask import Flask

from .extensions import db
from .seed import seed_demo_data


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_cmd():
        db.create_all()
        click.echo("Database initialized.")

    @app.cli.command("seed")
    def seed_cmd():
        seed_demo_data()
        click.echo("Seeded demo data.")

