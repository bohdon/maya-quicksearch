
import pymel.core as pm
from Qt import QtCore, QtGui, QtWidgets

from core import SearchModelBase, SearchWindowBase
from core import maya_main_window


def show():
    if NodeSearchWindow.instance is None:
        NodeSearchWindow.instance = NodeSearchWindow(maya_main_window())
    NodeSearchWindow.instance.show()

def hide():
    if NodeSearchWindow.instance is not None:
        NodeSearchWindow.instance.close()



class NodeSearchModel(SearchModelBase):
    """
    A SearchModelBase object that searches for nodes in the maya scene
    """

    def __init__(self, parent=None):
        super(NodeSearchModel, self).__init__(parent)
        # cached list of nodes for faster searching
        # only needs to be updated when nodeKwargs change
        self.cachedNodeList = []
        # kwargs to be given to the `ls` command when retrieving nodes
        # used to filter the results even before the main search query is used
        self.nodeKwargs = dict(
            recursive=True,
            long=True,
        )

    def getItemDisplayRoleData(self, index):
        """
        Return the result at the index, split from a long node name to a short name
        """
        return self.results[index.row()].split('|')[-1]

    def _updateResults(self):
        """
        Perform a simple string-contains search
        on the cached node list and store as results
        """
        self.results = [n for n in self.cachedNodeList if self.query in n.lower()]

    def forceUpdateResults(self):
        """
        Update both the cached node list and the search results.
        """
        self._updateCachedNodeList()
        super(NodeSearchModel, self).forceUpdateResults()

    def _updateCachedNodeList(self):
        """
        Perform the node list in maya and cache the results
        """
        args = ['*']
        self.cachedNodeList = sorted(pm.cmds.ls(*args, **self.nodeKwargs))

    def setNodeKwargs(self, **kwargs):
        """
        Set one or more node list kwargs and force update the search results
        """
        for key in kwargs:
            if key in self.nodeKwargs:
                self.nodeKwargs[key] = kwargs[key]
        self.forceUpdateResults()



class NodeSelectionModel(QtCore.QItemSelectionModel):
    """
    Selection model that is responsible for selecting nodes
    in the scene when they are selected in the search window list.
    """

    def __init__(self, parent=None):
        super(NodeSelectionModel, self).__init__(parent)
        parent.dataChanged.connect(self.updateSelection)
        self.selectionChanged.connect(self.updateSceneSelection)

    def updateSelection(self, topLeft=None, bottomRight=None):
        self.reset()
        sel = pm.cmds.ls(sl=True, long=True)
        results = self.model().results
        # block signals so they dont recursively affect selection
        self.blockSignals(True)
        for s in sel:
            if s in results:
                i = self.model().index(results.index(s))
                self.select(i, QtCore.QItemSelectionModel.SelectionFlag.Select)
        self.blockSignals(False)

    def updateSceneSelection(self):
        results = self.model().results
        # get nodes at matching indeces of the results
        nodes = [results[i.row()] for i in self.selectedRows()]
        pm.select(nodes)





class NodeSearchWindow(SearchWindowBase):
    """
    A simple search window that searches for nodes in the maya scene.
    Supports various node listing kwargs (given to cmds.ls command).
    """

    # static instance of a NodeSearchWindow for persistent use
    instance = None

    def __init__(self, parent=None):
        super(NodeSearchWindow, self).__init__(parent)
        # create custom selection model to link selection in maya scene
        self.nodeSelection = NodeSelectionModel(self.searchModel)
        self.listView.setSelectionModel(self.nodeSelection)

    def getDesiredObjectName(self): # override
        return "maya_quicksearch_nodesearchwindow"

    def getNewSearchModel(self): # override
        return NodeSearchModel(self)