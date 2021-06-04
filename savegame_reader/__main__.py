import click
import json

from openttd_helpers import click_helper

from .savegame import Savegame
from .gui import SavegameBrowser


@click_helper.command()
@click.argument("savegame", nargs=1, type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("--export-json", help="Export the savegame as JSON.", is_flag=True)
def main(savegame, export_json):
    sg = Savegame(savegame)

    with open(sg.filename, "rb") as fp:
        sg.read(fp)

    if export_json:
        print(json.dumps(sg.tables))
        return

    SavegameBrowser(sg).run()


if __name__ == "__main__":
    main()
