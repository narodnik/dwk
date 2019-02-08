import QtQuick 2.12
import QtQuick.Controls 2.5
import QtQuick.Layouts 1.12
import QtWebEngine 1.0

ApplicationWindow {
    id: window
    width: 1024
    height: 750
    visible: true

    readonly property bool inPortrait: window.width < window.height

    menuBar: MenuBar {
        Menu {
            title: "File"
            MenuItem { text: "Open" }
            MenuItem { text: "Close" }
        }

        Menu {
            title: "Edit"
            MenuItem { text: "Cut" }
            MenuItem { text: "Copy" }
            MenuItem { text: "Paste" }
        }
    }

    header: ToolBar {
        RowLayout {
            anchors.fill: parent
            ToolButton {
                icon.source: "icons/new.png"
            }
            ToolButton {
                icon.source: "icons/open.png"
            }
            ToolButton {
                icon.source: "icons/save.png"
            }
            Item { Layout.fillWidth: true }
            CheckBox {
                text: "Enabled"
                checked: true
                Layout.alignment: Qt.AlignRight
            }
        }
    }

    StackView {
        id: page
        anchors.fill: parent

        SwipeView {
            id: swipeView
            anchors.fill: parent
            currentIndex: tabBar.currentIndex


            WebEngineView {
                width: swipeView.width
                height: swipeView.height
                url: "./build/main.html"

                onUrlChanged: {
                    console.log(url);
                    //url = "./build/main.html"
                    //swipeView.currentIndex = 1

                    var result = String(url).split(":")
                    if (result[0] == "edit")
                        console.log("hello")
                }
            }
            /*ScrollView {
                width: swipeView.width
                height: swipeView.height
                
                TextEdit {
                    width: swipeView.width
                    height: swipeView.height
                    text: html_output.text
                    textFormat: TextEdit.RichText
                }
            }*/

            ScrollView {
                width: swipeView.width
                height: swipeView.height
                
                TextArea {
                    id: editor
                    text: source_text.text
                    font.family: "monospace"
                }
            }

            Pane {
                width: swipeView.width
                height: swipeView.height

                Column {
                    spacing: 40
                    width: parent.width

                    Label {
                        width: parent.width
                        wrapMode: Label.Wrap
                        horizontalAlignment: Qt.AlignHCenter
                        text: "bbbTabBar is a bar with icons or text which allows the user"
                              + "to switch between different subtasks, views, or modes."
                    }

                    Image {
                        source: "./arrows.png"
                        anchors.horizontalCenter: parent.horizontalCenter
                    }
                }
            }
        }
    }

    footer: TabBar {
        id: tabBar
        currentIndex: swipeView.currentIndex

        TabButton {
            text: "Article"
        }
        TabButton {
            text: "Edit"
        }
        TabButton {
            text: "History"
        }
    }
}

