from app.tools.read_admin import (
    get_interface,
    get_interface_config,
    get_page,
    get_project,
    list_interface_versions,
    list_interfaces,
    list_page_versions,
    list_pages,
    list_projects,
)

_tools = [
    list_projects,
    list_pages,
    list_interfaces,
    get_project,
    get_page,
    get_interface,
    get_interface_config,
    list_page_versions,
    list_interface_versions,
]


def get_tools() -> list:
    return _tools


def get_tool_names() -> list[str]:
    return [t.name for t in _tools]
