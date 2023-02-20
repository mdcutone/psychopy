# -*- coding: utf-8 -*-
"""Extra utilities supporting the plugin GUI interface.
"""

import requests


def getAllPluginDetails():
    """Get information about available plugins.

    This downloads the `plugins.json` file from `psychopy.org` and parses it to
    get our list of curated plugins.

    Returns
    -------
    list or None
        List of mappings (`dict`) of plugin information. If `None`, plugin
        information was not accessible.

    """
    # based on Todd's original implementation
    # Request plugin info list from server
    resp = requests.get("https://psychopy.org/plugins.json")
    # If 404, return None so the interface can handle this nicely rather than an
    # unhandled error.
    if resp.status_code == 404:
        return

    # Create PluginInfo objects from info list
    objs = []
    for info in resp.json():
        objs.append(info)

    return objs


if __name__ == "__main__":
    pass
