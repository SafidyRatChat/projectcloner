def classFactory(iface):
    from .project_cloner import ProjectCloner
    return ProjectCloner(iface)