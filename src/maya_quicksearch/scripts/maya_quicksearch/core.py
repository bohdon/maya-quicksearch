

import maya.OpenMayaUI as omui
from Qt import QtCore, QtGui, QtWidgets


__all__ = [
    'maya_main_window',
    'SearchModelBase',
    'SearchWindowBase',
]


def maya_main_window():
    """
    Return Mayas main window
    """
    for obj in QtWidgets.qApp.topLevelWidgets():
        if obj.objectName() == 'MayaWindow':
            return obj
    raise RuntimeError('Could not find MayaWindow instance')



class SearchModelBase(QtCore.QAbstractListModel):

    def __init__(self, parent=None):
        super(SearchModelBase, self).__init__(parent)

        # current number of items being displayed
        self.numItemsDisplayed = 0
        # number of items to initially display before fetching more
        self.numItemsInitiallyDisplayed = 100
        # number of items to fetch at once when requesting more results
        self.numItemsToFetch = 25

        # the current search query
        self.query = None
        # the current list of results
        self.results = []

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
            return self.getItemDisplayRoleData(index)
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
        Set the current search query and update the search results accordingly.
        """
        if query is not None:
            self.query = query
        self._updateResultsInternal()

    def forceUpdateResults(self):
        """
        Refreshes the current results.
        """
        self._updateResultsInternal()

    def _updateResultsInternal(self):
        """
        Update the current list of results by calling _updateResults.

        Returns True if the results have changed.
        """
        lastResults = self.results
        if not self.query:
            self.results = []
        else:
            self._updateResults()
        if self.results != lastResults:
            self.numItemsDisplayed = min(len(self.results), self.numItemsInitiallyDisplayed)
            self.dataChanged.emit(QtCore.QModelIndex(), QtCore.QModelIndex(), None)

    def getItemDisplayRoleData(self, index):
        """
        Return the DisplayRole data for the item at the given index
        """
        raise NotImplementedError

    def _updateResults(self):
        """
        Update self.results using the current search query.
        Should be overridden by base classes, self.results must always be a list.
        """
        raise NotImplementedError





class SearchWindowBase(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(SearchWindowBase, self).__init__(parent)
        self.setObjectName(self.getDesiredObjectName())

        # whether this window can be moved by dragging anywhere on it
        self.dragAnywhere = True
        # whether this window closes when it loses focus
        self.closeOnLoseFocus = True

        # build the core ui of the window, shared by all subclasses
        self.setupUi(self)
        # register for custom event filter
        self.installEventFilter(self)

        # create search model and connect it to the list view
        self.searchModel = self.getNewSearchModel()
        self.listView.setModel(self.searchModel)

        # connect search field to the model
        self.inputField.textChanged.connect(self.inputChanged)
        # self.searchModel.dataChanged.connect(self.updateStatus)

        # QtCore.QObject.connect(self.settingsButton, QtCore.SIGNAL("toggled(bool)"), self.settings.setVisible)
        # QtCore.QMetaObject.connectSlotsByName(self)
        self.setTabOrder(self.inputField, self.listView)
        self.setTabOrder(self.listView, self.inputField)
        # self.setTabOrder(self.lsSearchField, self.lsTypesField)
        # self.setTabOrder(self.lsTypesField, self.settingsButton)

    def getDesiredObjectName(self):
        """
        Return the object name that should be set for this window
        Should be overridden in subclasses
        """
        raise NotImplementedError

    def getNewSearchModel(self):
        """
        Return a new instance of a SearchModelBase type to use
        for this window.
        Should be overridden in subclasses
        """
        raise NotImplementedError

    def eventFilter(self, obj, event):
        t = event.type()

        if self.dragAnywhere:
            # since this is a frameless window, allow dragging anywhere on window body
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

        if self.closeOnLoseFocus:
            # close the window when it loses focus
            if t == QtCore.QEvent.Type.WindowDeactivate:
                self.close()

        try:
            return QtCore.QObject.eventFilter(self, obj, event)
        except:
            return False

    def inputChanged(self, text):
        self.searchModel.setQuery(text)

    def show(self):
        """
        Reset search model and show the window
        """
        self.inputField.setFocus()
        self.inputField.selectAll()
        self.inputField.setText('')
        # force an update on the search model
        self.searchModel.forceUpdateResults()
        super(SearchWindowBase, self).show()
        self.activateWindow()

    def setupUi(self, parent):
        """
        Build the UI for this window
        """
        self.resize(300, 400)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setSizeGripEnabled(True)

        self.verticalLayout = QtWidgets.QVBoxLayout(parent)
        self.verticalLayout.setSpacing(8)
        self.verticalLayout.setContentsMargins(10, 10, 10, 10)

        # search query input field
        self.inputField = QtWidgets.QLineEdit(parent)
        self.inputField.setMaxLength(512)
        self.verticalLayout.addWidget(self.inputField)

        # results list view
        self.listView = QtWidgets.QListView(parent)
        self.listView.setAlternatingRowColors(True)
        self.listView.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.listView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.verticalLayout.addWidget(self.listView)
