from PySide6.QtWidgets import QListWidget
from PySide6.QtCore import Qt

from shell_delta import gb_var as gb_var_script

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class LayerListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.opengl_widget = None

    def keyPressEvent(self, event):
        _layer_op_keys = [
            Qt.Key.Key_U,
            Qt.Key.Key_D,
            Qt.Key.Key_H, 
            Qt.Key.Key_S,
            Qt.Key.Key_T
        ]
        pressed = event.key()
        modifier = event.modifiers()

        if pressed in _layer_op_keys :
            selected_item = self.currentItem()
            if not selected_item:
                return
            selected_item_idx = self.currentRow()
            if pressed == Qt.Key.Key_U:
                if selected_item_idx <= 0:
                    return
                self.takeItem(selected_item_idx)
                self.insertItem(selected_item_idx - 1, selected_item)
                layer_order = gb_var_full.layer_order
                item = layer_order.pop(selected_item_idx)
                layer_order.insert(selected_item_idx - 1,item)
                gb_var_full.restack_layers(
                    new_layer_order=layer_order,
                    new_active_layer=selected_item_idx - 1
                )
                self.setCurrentRow(selected_item_idx - 1)
                self.opengl_widget.update()
            elif pressed == Qt.Key.Key_D:
                if selected_item_idx >= self.count() - 1:
                    return
                self.takeItem(selected_item_idx)
                self.insertItem(selected_item_idx + 1, selected_item)
                layer_order = gb_var_full.layer_order
                item = layer_order.pop(selected_item_idx)
                layer_order.insert(selected_item_idx + 1,item)
                gb_var_full.restack_layers(
                    new_layer_order=layer_order,
                    new_active_layer=selected_item_idx + 1
                )
                self.setCurrentRow(selected_item_idx + 1)
                self.opengl_widget.update()
                
            elif pressed == Qt.Key.Key_H:
                if self.opengl_widget is None:
                    return
                if (modifier & Qt.KeyboardModifier.ShiftModifier):
                    self.opengl_widget.toggle_layer_visibility(
                        target_layer=selected_item_idx,
                        mode=2
                    )
                elif (modifier & Qt.KeyboardModifier.AltModifier):
                    self.opengl_widget.toggle_layer_visibility(
                        target_layer=selected_item_idx,
                        mode=3
                    )
                else:
                    self.opengl_widget.toggle_layer_visibility(
                        target_layer=selected_item_idx,
                        mode=1
                    )

            elif pressed == Qt.Key.Key_S:
                if self.opengl_widget is None:
                    return
                self.opengl_widget.switch_size_standard(new_idx=self.currentRow())

            elif pressed == Qt.Key.Key_T:
                print("Hello")