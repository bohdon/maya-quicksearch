

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
    for obj in QtWidgets.QApplication.instance().topLevelWidgets():
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

    def index(self, row, column=0, parent=None): # override
        return self.createIndex(row, column)

    def parent(self, index=None): # override
        return QtCore.QModelIndex()

    def rowCount(self, parent=None): # override
        return self.numItemsDisplayed

    def columnCount(self, parent=None): # override
        return 1

    def data(self, index, role=QtCore.Qt.DisplayRole): # override
        if not index.isValid():
            return
        if index.row() >= self.rowCount() or index.row() < 0:
            return
        return self.getItemData(index, role)

    def getItemData(self, index, role=QtCore.Qt.DisplayRole):
        """
        Return data for the item for the given role.
        The index has already been validated and does not need
        to be checked in subclasses.
        """
        raise NotImplementedError

    def getStatusText(self):
        """
        Return a text string containing information about the current
        search results. Returns the length of the results by default.
        Override in subclass to add more customized information
        """
        return len(self.results)

    def canFetchMore(self, parent): # override
        return self.numItemsDisplayed < len(self.results)

    def fetchMore(self, parent): # override
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
        self._updateResultsInternal(True)

    def _updateResultsInternal(self, forceEmitChange=False):
        """
        Update the current list of results by calling _updateResults.

        Returns True if the results have changed.
        """
        lastResults = self.results
        if not self.query:
            self.results = []
        else:
            self._updateResults()
        if self.results != lastResults or forceEmitChange:
            self.numItemsDisplayed = min(len(self.results), self.numItemsInitiallyDisplayed)
            self.dataChanged.emit(QtCore.QModelIndex(), QtCore.QModelIndex(), None)

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

        # register for custom event filter
        self.installEventFilter(self)

        # build the core ui of the window, shared by all subclasses
        self.setupUi(self)
        
        # disable the options button by default,
        # enable this and build a ui parented to self.optionsWidget in subclasses if desired
        self.optionsBtn.setVisible(False)
        self.optionsBtn.toggled.connect(self.optionsWidget.setVisible)

        # create search model and connect it to the list view
        self.searchModel = self.getNewSearchModel()
        self.searchModel.dataChanged.connect(self.updateStatusLabel)
        self.listView.setModel(self.searchModel)
        # connect input field to the search query
        self.inputField.textChanged.connect(self.searchModel.setQuery)

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

    def eventFilter(self, obj, event): # override
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

    def show(self): # override
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

    def updateStatusLabel(self):
        self.statusLabel.setText(str(self.searchModel.getStatusText()))

    def setupUi(self, parent):
        """
        Build the UI for this window
        """
        self.resize(380, 500)
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setSizeGripEnabled(True)

        self.verticalLayout = QtWidgets.QVBoxLayout(parent)
        self.verticalLayout.setSpacing(8)
        self.verticalLayout.setContentsMargins(10, 10, 10, 10)
        self.verticalLayout.setObjectName("verticalLayout")

        # title bar HBox layout
        self.titleLayout = QtWidgets.QHBoxLayout(parent)
        self.verticalLayout.addLayout(self.titleLayout)
        # title text to replace frameless window title
        self.titleLabel = QtWidgets.QLabel(parent)
        self.titleLabel.setObjectName("titleLabel")
        self.titleLayout.addWidget(self.titleLabel)
        # options button
        self.optionsBtn = QtWidgets.QPushButton(parent)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        self.optionsBtn.setSizePolicy(sizePolicy)
        self.optionsBtn.setMaximumSize(QtCore.QSize(30, 30))
        self.optionsBtn.setCheckable(True)
        self.optionsBtn.setText('...')
        self.optionsBtn.setVisible(False)
        self.optionsBtn.setObjectName("optionsBtn")
        self.titleLayout.addWidget(self.optionsBtn)

        # search query input field
        self.inputField = QtWidgets.QLineEdit(parent)
        self.inputField.setMaxLength(512)
        self.inputField.setObjectName("inputField")
        self.verticalLayout.addWidget(self.inputField)

        # selectable list view for showing all results
        self.listView = QtWidgets.QListView(parent)
        self.listView.setAlternatingRowColors(True)
        self.listView.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.listView.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.listView.setObjectName("listView")
        self.verticalLayout.addWidget(self.listView)

        # options widget that will contain a customizeable ui
        # designed to be unique for each search window
        self.optionsWidget = QtWidgets.QWidget(parent)
        self.optionsWidget.setVisible(False)
        self.optionsWidget.setObjectName("optionsWidget")
        self.verticalLayout.addWidget(self.optionsWidget)

        # status text for displaying result count or other info
        self.statusLabel = QtWidgets.QLabel(parent)
        self.statusLabel.setObjectName("statusLabel")
        self.verticalLayout.addWidget(self.statusLabel)
