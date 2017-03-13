
import argparse
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



class SilentArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser with silent erroring and no exiting
    """
    def exit(self, status=0, message=None): # override
        pass

    def error(self, message): # override
        pass



class NodeSearchModel(SearchModelBase):
    """
    A SearchModelBase object that searches for nodes in the maya scene
    """

    def __init__(self, parent=None):
        super(NodeSearchModel, self).__init__(parent)
        # cached list of nodes for faster searching
        # only needs to be updated when nodeKwargs change
        self.cachedNodeList = []

        # `ls` command kwargs that are necessary for the search to work
        self.persistentNodeKwargs = dict(
            long=True, recursive=True
        )
        # `ls` command kwargs that can be set by the user
        self.nodeKwargs = {}
        # `ls` command kwargs that are gathered from the search query
        self.nodeKwargsFromQuery = {}

        # list of `ls` boolean kwargs that can be set by the user
        self.boolNodeKwargKeys = [
            'assemblies', 'cameras', 'dagObjects',
            'geometry', 'invisible', 'lights',
            'live', 'lockedNodes', 'materials',
            'modified', 'partitions', 'planes',
            'readOnly', 'referencedNodes', 'selection',
            'sets', 'shapes', 'textures',
            'transforms', 'untemplated', 'visible',
        ]
        # list of `ls` kwargs that expect node types as values
        self.typeNodeKwargKeys = [
            'type', 'exactType', 'excludeType'
        ]
        self.allValidKwargKeys = self.boolNodeKwargKeys + self.typeNodeKwargKeys
        # mapping of short names to long names for accepted ls flags
        self.nodeKwargLongNameMap = {
            'ca':'cameras', 'dag':'dagObjects',
            'g':'geometry', 'iv':'invisible', 'lt':'lights',
            'lv':'live', 'ln':'lockedNodes', 'mat':'materials',
            'mod':'modified', 'pr':'partitions', 'pl':'planes',
            'ro':'readOnly', 'rn':'referencedNodes', 'sl':'selection',
            'set':'sets', 's':'shapes', 'tex':'textures',
            'tr':'transforms', 'ut':'untemplated', 'v':'visible',
            # query kwargs long name mapping
            'typ':'type', 'et':'exactType', 'ext':'excludeType',
        }
        # define common set of node kwargs to be listed as options
        self.commonNodeKwargKeys = [
            'transforms', 'shapes', 'lights',
            'cameras', 'materials', 'textures',
            'geometry', 'dagObjects', 'selection'
        ]
        # setup an arg parser for the search query to handle advanced kwargs
        allNodeTypes = pm.cmds.allNodeTypes()
        self.queryParser = SilentArgumentParser(prog='maya_quicksearch_nodesearch')
        for key in self.boolNodeKwargKeys:
            self.queryParser.add_argument('-{0}'.format(key), action='store_true')
        for key in self.typeNodeKwargKeys:
            self.queryParser.add_argument('-{0}'.format(key), choices=allNodeTypes, nargs='+')
        for key, val in self.nodeKwargLongNameMap.items():
            if val in self.boolNodeKwargKeys:
                self.queryParser.add_argument('-{0}'.format(key), dest=val, action='store_true')
            elif val in self.typeNodeKwargKeys:
                self.queryParser.add_argument('-{0}'.format(key), dest=val, choices=allNodeTypes, nargs='+')

    def resetNodeKwargs(self):
        """
        Reset user customizeable node kwargs to their defaults
        """
        self.nodeKwargs = {}
        self.forceUpdateResults()

    def getNodeKwargValue(self, key):
        """
        Return the current value that will be given for a
        node kwarg key. Considers all node kwargs.
        """
        if key in self.nodeKwargLongNameMap:
            key = self.nodeKwargLongNameMap[key]
        kwargs = self.getFullNodeKwargs()
        if key in kwargs:
            return kwargs[key]

    def getFullNodeKwargs(self):
        """
        Return the combine set of node kwargs that will be used
        to retrieve the full list of nodes.
        """
        result = {}
        result.update(self.nodeKwargsFromQuery)
        result.update(self.nodeKwargs)
        result.update(self.persistentNodeKwargs)
        return result

    def setNodeKwargs(self, **kwargs):
        """
        Set one or more user customizeable node kwargs.
        """
        didChange = False
        lastNodeKwargs = self.nodeKwargs.copy()
        self._setNodeKwargsInternal(self.nodeKwargs, **kwargs)
        if lastNodeKwargs != self.nodeKwargs:
            self.forceUpdateResults()

    def _setNodeKwargsInternal(self, obj, **kwargs):
        """
        Set node kwargs on the given object.
        Convert short name flags to long ones and
        make sure the keys are valid node kwargs.
        Also prunes values that are defaults.
        """
        for key, val in kwargs.items():
            # convert to long name if applicable
            if key in self.nodeKwargLongNameMap:
                key = self.nodeKwargLongNameMap[key]
            # make sure its a valid key
            if key in self.allValidKwargKeys:
                if val:
                    obj[key] = val
                elif key in obj:
                    del obj[key]


    def getItemData(self, index, role=QtCore.Qt.DisplayRole): # override
        """
        Return the result at the index, split from a long node name to a short name
        """
        longName = self.results[index.row()]
        if role == QtCore.Qt.DisplayRole:
            shortName = longName.split('|')[-1]
            return shortName

    def _updateResults(self): # override
        """
        Perform a simple string-contains search
        on the cached node list and store as results
        """
        lastQueryKwargs = self.nodeKwargsFromQuery.copy()
        queryBody, self.nodeKwargsFromQuery = self.parseQueryString(self.query)
        if lastQueryKwargs != self.nodeKwargsFromQuery:
            # kwargs have changed, we need to update the node list
            self._updateCachedNodeList()
        if queryBody or self.nodeKwargsFromQuery:
            # create results if kwargs exist, even if main query is empty
            self.results = [n for n in self.cachedNodeList if queryBody.strip() in n.lower()]
        else:
            self.results = []

    def parseQueryString(self, queryString):
        """
        Parse the given query string and return its body and kwargs.
        Uses an arg parser, but retrieves the body by simply splitting at the first
        '-' character so that if the argparser fails we still have a body.

        >>> parseQueryString('my search -flag1 -flag2 -invalidFlag ignored text')
        ('my search', {'flag1': True, 'flag2': True})

        Returns:
            `str`, `dict`
                query body, query kwargs
        """
        argsIndex = queryString.find('-')
        if argsIndex < 0:
            # no kwargs
            return queryString, {}
        # split into body and args string
        resultBody = queryString[:argsIndex]
        queryArgsString = queryString[argsIndex:]
        resultKwargs = {}
        try:
            # run argparser on the rest of the query string
            result = self.queryParser.parse_known_args(queryArgsString.split(' '))
            if result:
                # break result into parsed args and unknown
                args, unknown = result
                self._setNodeKwargsInternal(resultKwargs, **dict(args._get_kwargs()))
                # prune any values that already exist in nodeKwargs,
                # or aren't valid values
                for key, val in resultKwargs.items():
                    if key in self.nodeKwargs and val == self.nodeKwargs[key]:
                        del resultKwargs[key]
                    elif key in self.typeNodeKwargKeys and val is None:
                        del resultKwargs[key]
        except Exception as e:
            import inspect
            print(inspect.stack())
            print(e)
        return resultBody, resultKwargs

    def forceUpdateResults(self): # override
        """
        Update both the cached node list and the search results.
        """
        self._updateCachedNodeList()
        super(NodeSearchModel, self).forceUpdateResults()

    def getStatusText(self):
        """
        Return the results count as well as the current node list kwargs
        """
        def formatKwarg(key, value):
            if key in self.typeNodeKwargKeys:
                return '-{0} {1}'.format(key, ' '.join(list(value)))
            elif value is True:
                return '-{0}'.format(key)
            return ''

        count = len(self.results)
        # show non-default `ls` command kwargs
        flags = [formatKwarg(k, v) for k, v in self.getFullNodeKwargs().items() if v and k not in self.persistentNodeKwargs]
        if flags:
            return '{0} ( {1} )'.format(count, ' '.join(flags))
        else:
            return count

    def _updateCachedNodeList(self):
        """
        Perform the node list in maya and cache the results
        """
        try:
            nodes = pm.cmds.ls('*', **self.getFullNodeKwargs())
        except:
            nodes = []
        self.cachedNodeList = sorted(nodes)
        # emitting data change even though it might be called again later
        # because we want accurate status text, etc
        self.dataChanged.emit(QtCore.QModelIndex(), QtCore.QModelIndex(), None)




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
        # update window title
        self.titleLabel.setText("Node Search")
        # enable options widget
        self.optionsBtn.setVisible(True)
        self.setupOptionsUi(self.optionsWidget)
        # create custom selection model to link selection in maya scene
        self.nodeSelection = NodeSelectionModel(self.searchModel)
        self.listView.setSelectionModel(self.nodeSelection)

    def getDesiredObjectName(self): # override
        return "maya_quicksearch_nodesearchwindow"

    def getNewSearchModel(self): # override
        return NodeSearchModel(self)

    def setNodeKwargForSimpleType(self, button, toggled):
        """
        Update search model node kwargs based on the toggled
        state of the given button.

        Args:
            button : `QAbstractButton`
            toggle : `bool`
        """
        # button object names are of the format 'nodeKwargBtn_[key]'
        key = button.objectName()[13:]
        self.searchModel.setNodeKwargs(**{key:toggled})

    def setupOptionsUi(self, parent): # override
        """
        Build options UI containing different preset filter types
        """
        self.optsVLayout = QtWidgets.QVBoxLayout(parent)
        self.optsVLayout.setObjectName("optsVLayout")

        self.optsSimpleTypesGrid = QtWidgets.QGridLayout(parent)
        # self.optsSimpleTypesGrid.setSpacing(8)
        self.optsSimpleTypesGrid.setContentsMargins(0, 0, 0, 0)
        self.optsVLayout.addLayout(self.optsSimpleTypesGrid)

        # create a grid of buttons for toggling some basic node kwargs
        btnGroup = QtWidgets.QButtonGroup(parent)
        btnGroup.setExclusive(False)
        btnGroup.buttonToggled.connect(self.setNodeKwargForSimpleType)
        numColumns = 3
        row, col = 0, 0
        for key in self.searchModel.commonNodeKwargKeys:
            btn = QtWidgets.QPushButton(parent)
            btn.setObjectName('nodeKwargBtn_{0}'.format(key))
            btn.setCheckable(True)
            btn.setChecked(QtCore.Qt.Checked if self.searchModel.getNodeKwargValue(key) else QtCore.Qt.Unchecked)
            btn.setText(key.title())
            btnGroup.addButton(btn)
            self.optsSimpleTypesGrid.addWidget(btn, row, col)
            col += 1
            if col >= numColumns:
                col = 0
                row += 1

        # create a custom flags input field for more granular control
        self.optsNodeKwargsAdvancedLabel = QtWidgets.QLabel(parent)
        self.optsNodeKwargsAdvancedLabel.setWordWrap(True)
        self.optsNodeKwargsAdvancedLabel.setText('additional flags are supported: e.g. `-type joint`')
        self.optsNodeKwargsAdvancedLabel.setObjectName('optsNodeKwargsAdvancedLabel')
        self.optsVLayout.addWidget(self.optsNodeKwargsAdvancedLabel)
