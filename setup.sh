#! bash



if [[ ! "$MAYA_MODULES_INSTALL_PATH" ]]; then
	if [[ "$(uname)" == "Darwin" ]]; then
		MAYA_MODULES_INSTALL_PATH="$HOME/Library/Preferences/Autodesk/maya/modules"
	elif [[ "$(expr substr $(uname -s) 1 5)" == "Linux" ]]; then
		MAYA_MODULES_INSTALL_PATH="/usr/autodesk/userconfig/maya/modules"
	elif [[ "$(expr substr $(uname -s) 1 5)" == "MINGW" ]]; then
		IS_WINDOWS=1
		MAYA_MODULES_INSTALL_PATH="$HOME/Documents/maya/modules"
	fi
fi



build() {
	mkdir -p build
	cp -R src/maya_quicksearch build/
	cp -R src/maya_quicksearch.mod build/
}

clean() {
	rm -Rf build
}

dev() {
	uninstall
	clean
	link `pwd`/src/maya_quicksearch.mod $MAYA_MODULES_INSTALL_PATH/maya_quicksearch.mod
	link `pwd`/src/maya_quicksearch $MAYA_MODULES_INSTALL_PATH/maya_quicksearch
}

install() {
	uninstall
	clean
	build
	cp -v build/maya_quicksearch.mod $MAYA_MODULES_INSTALL_PATH/maya_quicksearch.mod
	cp -Rv build/maya_quicksearch $MAYA_MODULES_INSTALL_PATH/maya_quicksearch
}

uninstall() {
	rm -v $MAYA_MODULES_INSTALL_PATH/maya_quicksearch.mod
	rm -Rv $MAYA_MODULES_INSTALL_PATH/maya_quicksearch
}


ALL_COMMANDS="build, clean, dev, install, uninstall"



# Template setup.sh utils
# -----------------------


# simple cross-platform symlink util
link() {
	# use mklink if on windows
	if [[ -n "$WINDIR" ]]; then
		# determine if the link is a directory
		# also convert '/' to '\'
		if [[ -d "$1" ]]; then
			cmd <<< "mklink /D \"`cygpath -w $2`\" \"`cygpath -w $1`\"" > /dev/null
		else
			cmd <<< "mklink \"`cygpath -w $2`\" \"`cygpath -w $1`\"" > /dev/null
		fi
	else
		ln -sf "$1" "$2"
	fi
}

# run command by name
if [[ "$1" ]]; then
	cd $(dirname "$0")
	$1
else
	echo -e "usage: setup.sh [COMMAND]\n  $ALL_COMMANDS"
fi