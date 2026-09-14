# -*- coding: utf-8 -*-
"""
CloudCompare PythonRuntime plugin for CloudCompare 2.13.x.

Workflow:
1) Select one source point cloud A in DB Tree -> Set source cloud A.
2) Select one or more point-cloud instances in DB Tree -> Add selected bounding boxes.
3) Apply -> remove all points of A that fall inside ANY selected bounding box.

Bounding boxes are axis-aligned (AABB) in CloudCompare's XYZ coordinate frame.
"""

import numpy as np
import pycc
import cccorelib

try:
    from bbox_core import BoxSpec, add_unique_box, compute_keep_mask
except ImportError:
    # Some PythonRuntime custom-plugin loaders import a .py file without first
    # putting its directory on sys.path. Make the sibling helper import robust.
    import os
    import sys
    _plugin_dir = os.path.dirname(os.path.abspath(__file__))
    if _plugin_dir not in sys.path:
        sys.path.insert(0, _plugin_dir)
    from bbox_core import BoxSpec, add_unique_box, compute_keep_mask


class MultiBoxRemovePlugin(pycc.PythonPluginInterface):
    def __init__(self):
        super().__init__()
        self.app = pycc.GetInstance()
        self.source_cloud = None
        self.source_id = None
        self.boxes = []

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log(self, msg):
        try:
            pycc.ccLog.Print("[MultiBoxRemove] " + str(msg))
        except Exception:
            print("[MultiBoxRemove] " + str(msg))

    def _warn(self, msg):
        try:
            pycc.ccLog.Warning("[MultiBoxRemove] " + str(msg))
        except Exception:
            print("[MultiBoxRemove][WARNING] " + str(msg))

    def _error(self, msg):
        try:
            pycc.ccLog.Error("[MultiBoxRemove] " + str(msg))
        except Exception:
            print("[MultiBoxRemove][ERROR] " + str(msg))

    # ------------------------------------------------------------------
    # Entity / bounding-box helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_editable_point_cloud(entity):
        # Source A must support raw point access and partialClone.
        return (
            hasattr(entity, "points")
            and hasattr(entity, "partialClone")
            and hasattr(entity, "getUniqueID")
        )

    @staticmethod
    def _can_supply_bbox(entity):
        # A bbox provider can be a point cloud (the intended use) or another
        # CloudCompare entity exposing the same getBoundingBox API.
        return (
            hasattr(entity, "getBoundingBox")
            and hasattr(entity, "getUniqueID")
            and hasattr(entity, "getName")
        )

    @staticmethod
    def _vec3_to_numpy(v):
        # CCVector3 bindings expose x/y/z as attributes in current builds.
        # Fallback to x()/y()/z() for compatibility with older wrappers.
        def component(name):
            value = getattr(v, name)
            if callable(value):
                value = value()
            return float(value)

        return np.array(
            [component("x"), component("y"), component("z")],
            dtype=np.float64,
        )

    def _entity_to_box(self, entity):
        bb_min = cccorelib.CCVector3()
        bb_max = cccorelib.CCVector3()
        entity.getBoundingBox(bb_min, bb_max)

        lo = self._vec3_to_numpy(bb_min)
        hi = self._vec3_to_numpy(bb_max)

        if not np.all(np.isfinite(lo)) or not np.all(np.isfinite(hi)):
            raise ValueError("Bounding box contains non-finite coordinates")

        return BoxSpec.from_corners(
            name=str(entity.getName()),
            source_key=str(int(entity.getUniqueID())),
            corner_a=lo,
            corner_b=hi,
        )

    def _print_box(self, box, index=None):
        dims = box.dimensions
        prefix = "包围框"
        if index is not None:
            prefix += " %d" % index
        self._log("%s: %s [ID=%s]" % (prefix, box.name, box.source_key))
        self._log(
            "  X: [%.9f, %.9f]  Length X = %.9f"
            % (box.lo[0], box.hi[0], dims[0])
        )
        self._log(
            "  Y: [%.9f, %.9f]  Length Y = %.9f"
            % (box.lo[1], box.hi[1], dims[1])
        )
        self._log(
            "  Z: [%.9f, %.9f]  Length Z = %.9f"
            % (box.lo[2], box.hi[2], dims[2])
        )

    # ------------------------------------------------------------------
    # Actions: source and boxes
    # ------------------------------------------------------------------
    def set_source_cloud(self):
        selected = self.app.getSelectedEntities()
        if len(selected) != 1:
            self._error("请在 DB Tree 中只选择一个源点云 A。")
            return

        cloud = selected[0]
        if not self._is_editable_point_cloud(cloud):
            self._error("选中对象不是可处理的 ccPointCloud。")
            return

        self.source_cloud = cloud
        self.source_id = int(cloud.getUniqueID())
        self.boxes = []

        self._log(
            "已设置源点云 A: %s [ID=%d, points=%d]"
            % (cloud.getName(), self.source_id, int(cloud.size()))
        )
        self._log("已清空旧包围框。现在可 Ctrl/Shift 多选用于定义包围框的点云实例。")

    def add_selected_bounding_boxes(self):
        if self.source_cloud is None:
            self._error("请先执行“1 - 设置源点云 A”。")
            return

        selected = self.app.getSelectedEntities()
        if not selected:
            self._error("请在 DB Tree 中选择一个或多个用于定义包围框的点云实例。")
            return

        added = 0
        skipped_source = 0
        skipped_duplicate = 0
        skipped_invalid = 0

        for entity in selected:
            if not self._can_supply_bbox(entity):
                self._warn("跳过不支持 Bounding Box 的对象: %s" % str(entity))
                skipped_invalid += 1
                continue

            try:
                entity_id = int(entity.getUniqueID())
            except Exception:
                self._warn("跳过无法读取 Unique ID 的对象: %s" % str(entity))
                skipped_invalid += 1
                continue

            if entity_id == self.source_id:
                self._warn("跳过源点云 A，不能把 A 自身作为删除包围框。")
                skipped_source += 1
                continue

            try:
                box = self._entity_to_box(entity)
            except Exception as exc:
                self._warn(
                    "读取 %s 的 Bounding Box 失败: %s"
                    % (getattr(entity, "getName", lambda: "<unknown>")(), exc)
                )
                skipped_invalid += 1
                continue

            if add_unique_box(self.boxes, box):
                added += 1
                self._print_box(box, len(self.boxes))
            else:
                self._warn("已存在，跳过重复包围框: %s [ID=%s]" % (box.name, box.source_key))
                skipped_duplicate += 1

        self._log(
            "添加完成：新增 %d，当前总数 %d；跳过源点云 %d，重复 %d，无效 %d。"
            % (
                added,
                len(self.boxes),
                skipped_source,
                skipped_duplicate,
                skipped_invalid,
            )
        )

    def list_bounding_boxes(self):
        if not self.boxes:
            self._warn("当前没有已添加的包围框。")
            return

        self._log("当前共有 %d 个包围框：" % len(self.boxes))
        for i, box in enumerate(self.boxes, 1):
            self._print_box(box, i)

    def clear_bounding_boxes(self):
        self.boxes = []
        self._log("已清空全部包围框；源点云 A 保持不变。")

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    @staticmethod
    def _build_reference_cloud(source_cloud, keep_indices):
        ref = cccorelib.ReferenceCloud(source_cloud)
        try:
            ref.reserve(int(len(keep_indices)))
        except Exception:
            pass

        # Individual insertion is slower than a native C++ visibility table,
        # but is the most compatible PythonRuntime 2.13.x path.
        for idx in keep_indices:
            if not ref.addPointIndex(int(idx)):
                raise RuntimeError(
                    "ReferenceCloud.addPointIndex failed at index %d" % int(idx)
                )
        return ref

    def remove_inside_all_boxes(self):
        if self.source_cloud is None:
            self._error("尚未设置源点云 A。")
            return
        if not self.boxes:
            self._error("尚未添加任何包围框。")
            return

        # Ensure the source entity still exists in the DB tree as far as its
        # Python wrapper can tell. Accessing points is also the final validity check.
        try:
            points = self.source_cloud.points()
        except Exception as exc:
            self._error("无法读取源点云 A；它可能已被删除或失效: %s" % exc)
            return

        if points is None or len(points) == 0:
            self._error("源点云 A 为空。")
            return

        total = int(points.shape[0])
        self._log(
            "开始处理：A=%s，点数=%d，包围框=%d"
            % (self.source_cloud.getName(), total, len(self.boxes))
        )

        try:
            keep_mask = compute_keep_mask(points, self.boxes)
        except Exception as exc:
            self._error("包围框过滤计算失败: %s" % exc)
            return

        keep_indices = np.flatnonzero(keep_mask)
        kept = int(keep_indices.size)
        removed = total - kept

        self._log(
            "空间过滤完成：删除 %d 点，保留 %d 点（%.3f%%）。"
            % (removed, kept, kept * 100.0 / total)
        )

        if removed == 0:
            self._warn("没有任何点落入这些包围框，未生成新点云。")
            return
        if kept == 0:
            self._warn("所有点都位于包围框并集内。为避免生成空点云，操作终止。")
            return

        try:
            ref = self._build_reference_cloud(self.source_cloud, keep_indices)
            result = self.source_cloud.partialClone(ref)
        except Exception as exc:
            self._error("创建结果点云失败: %s" % exc)
            return

        if result is None:
            self._error("partialClone 返回空结果。")
            return

        result.setName(
            "%s_OUTSIDE_%d_BBOXES"
            % (self.source_cloud.getName(), len(self.boxes))
        )

        try:
            self.app.addToDB(result)
            self.source_cloud.setEnabled(False)
            self.app.updateUI()
            self.app.redrawAll()
        except Exception as exc:
            self._error("结果已创建，但加入 DB Tree/刷新界面失败: %s" % exc)
            return

        self._log("完成：已保留全部包围框之外的点。")
        self._log("结果点云: %s" % result.getName())
        self._log("原始点云 A 仅隐藏，未删除。")

    # ------------------------------------------------------------------
    # PythonRuntime plugin menu
    # ------------------------------------------------------------------
    def getActions(self):
        return [
            pycc.Action(
                name="1 - 设置源点云 A",
                target=self.set_source_cloud,
            ),
            pycc.Action(
                name="2 - 添加所选点云的包围框",
                target=self.add_selected_bounding_boxes,
            ),
            pycc.Action(
                name="3 - 删除所有包围框内点",
                target=self.remove_inside_all_boxes,
            ),
            pycc.Action(
                name="查看当前包围框",
                target=self.list_bounding_boxes,
            ),
            pycc.Action(
                name="清空全部包围框",
                target=self.clear_bounding_boxes,
            ),
        ]
