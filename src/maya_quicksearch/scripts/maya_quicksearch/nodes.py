
import maya.OpenMayaUI as omui
import pymel.core as pm
from Qt import QtCore, QtGui, QtWidgets


import Qt
if Qt.__binding__ == 'PySide2':
    import pyside2uic as pysideuic
    from shiboken2 import wrapInstance
    # logging.Logger.manager.loggerDict["pysideuic.uiparser"].setLevel(logging.CRITICAL)
    # logging.Logger.manager.loggerDict["pysideuic.properties"].setLevel(logging.CRITICAL)
elif Qt.__binding__ == 'PySide':
    import pysideuic
    from shiboken import wrapInstance
    # logging.Logger.manager.loggerDict["pyside2uic.uiparser"].setLevel(logging.CRITICAL)
    # logging.Logger.manager.loggerDict["pyside2uic.properties"].setLevel(logging.CRITICAL)


def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)



_winInstance = None

def show():
    global _winInstance
    if _winInstance is None:
        _winInstance = NodeSearchWindow(maya_main_window())
    _winInstance.show()

def hide():
    if _winInstance is not None:
        _winInstance.close()




class NodeSearchModel(QtCore.QAbstractListModel):

    def __init__(self, parent=None):
        super(NodeSearchModel, self).__init__(parent)

        # current number of items being displayed
        self.numItemsDisplayed = 0
        # number of items to initially display until more are requested
        self.numItemsInitiallyDisplayed = 100
        # number of items to fetch when requesting more results
        self.numItemsToFetch = 25

        # the current search query
        self.query = None
        # the current list of results
        self.results = []

        # ----------

        # cached list of nodes
        self.nodes = []
        self.nodeKwargs = dict(
            recursive=True,
            long=True,
        )

    def index(self, row, column=0, parent=None):
        return self.createIndex(row, column)

    def parent(self, index=None):
        return QtCore.QModelIndex()

    def rowCount(self, parent=None):
        return self.numItemsDisplayed

    def columnCount(self, parent=None):
        return 1

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return
        if index.row() >= self.rowCount() or index.row() < 0:
            return
        if role == QtCore.Qt.DisplayRole:
            longName = self.results[index.row()]
            shortName = longName.split('|')[-1]
            return shortName

    def canFetchMore(self, parent):
        return self.numItemsDisplayed < len(self.results)

    def fetchMore(self, parent):
        numRemaining = len(self.results) - self.numItemsDisplayed
        fetchCount = min(self.numItemsToFetch, numRemaining)
        self.beginInsertRows(QtCore.QModelIndex(), self.numItemsDisplayed, self.numItemsDisplayed + fetchCount)
        self.numItemsDisplayed += fetchCount
        self.endInsertRows()

    def setQuery(self, query=None):
        """
        Set the current search query and updating the
        results data accordingly.
        """
        if query is not None:
            self.query = query
        resultsChanged = self._updateResults()
        if resultsChanged:
            self.numItemsDisplayed = min(len(self.results), self.numItemsInitiallyDisplayed)
            self.dataChanged.emit(QtCore.QModelIndex(), QtCore.QModelIndex(), None)

    def updatedCachedNodes(self):
        """
        Perform a search using the current node kwargs and
        cache the list for fast querying.
        """
        args = ['*']
        self.nodes = sorted(pm.cmds.ls(*args, **self.nodeKwargs) * 5)

    def searchPool(self):
        pass

    def _updateResults(self):
        """
        Update the current list of results using the cached node list
        and current search query string.

        Returns True if the results have changed.
        """
        results = self.results
        if not self.query:
            results = []
        else:
            results = [n for n in self.nodes if self.query in n.lower()]
        if self.results != results:
            self.results = results
            return True
        else:
            return False



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





class NodeSearchWindow(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(NodeSearchWindow, self).__init__(parent)
        self.setObjectName("maya_quicksearch_nodesearchwindow")

        self.buildUi()
        self.installEventFilter(self)

        # create search model and connect it to the list view
        self.searchModel = NodeSearchModel(self)
        self.nodeSelection = NodeSelectionModel(self.searchModel)
        self.listView.setModel(self.searchModel)
        self.listView.setSelectionModel(self.nodeSelection)
        # connect search field to the model
        # self.searchModel.dataChanged.connect(self.updateStatus)
        self.inputField.textChanged.connect(self.inputChanged)

        # QtCore.QObject.connect(self.settingsButton, QtCore.SIGNAL("toggled(bool)"), self.settings.setVisible)
        # QtCore.QMetaObject.connectSlotsByName(self)
        self.setTabOrder(self.inputField, self.listView)
        self.setTabOrder(self.listView, self.inputField)
        # self.setTabOrder(self.lsSearchField, self.lsTypesField)
        # self.setTabOrder(self.lsTypesField, self.settingsButton)


    def buildUi(self):
        self.resize(300, 400)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setSizeGripEnabled(True)

        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.verticalLayout.setSpacing(8)
        self.verticalLayout.setContentsMargins(10, 10, 10, 10)

        # search query input field
        self.inputField = QtWidgets.QLineEdit(self)
        self.inputField.setMaxLength(512)
        self.verticalLayout.addWidget(self.inputField)

        # results list view
        self.listView = QtWidgets.QListView(self)
        self.listView.setAlternatingRowColors(True)
        self.listView.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.listView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.verticalLayout.addWidget(self.listView)

    def inputChanged(self, text):
        self.searchModel.setQuery(text)

    def show(self):
        """
        Reset search model and show the window
        """
        self.searchModel.updatedCachedNodes()
        self.inputField.setFocus()
        self.inputField.selectAll()
        self.inputField.setText('')
        super(NodeSearchWindow, self).show()
        self.activateWindow()

    def eventFilter(self, obj, event):
        t = event.type()

        # handle mouse dragging events
        if t == QtCore.QEvent.MouseButtonPress:
            self._dragStart = self.pos()
            self._dragOffset = event.globalPos() - self._dragStart
            self._dragging = True
            return True
        elif t == QtCore.QEvent.MouseButtonRelease:
            self._dragging = False
            return True
        elif t in (QtCore.QEvent.MouseMove, QtCore.QEvent.TabletMove) and self._dragging:
            newPos = event.globalPos() - self._dragOffset
            self.move(newPos)
            return True
        elif t == QtCore.QEvent.Type.WindowDeactivate:
            self.close()

        try:
            return QtCore.QObject.eventFilter(self, obj, event)
        except:
            return False