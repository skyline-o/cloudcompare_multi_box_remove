# CloudCompare Multi-BBox Remove

一个基于 **CloudCompare PythonRuntime** 的点云裁剪工具，用于从源点云 **A** 中一次性删除多个三维包围框（Bounding Box）内部的点，并保留包围框外部点云。

与 CloudCompare 的二维 `Segmentation` 不同，本工具直接依据点的 **XYZ 三维坐标**进行判断，因此不会因为屏幕投影重叠而误删包围框前后方的点。

> 当前版本面向 **CloudCompare 2.13.x**，主要针对 **CloudCompare 2.13.2 / Windows 64-bit** 使用场景开发。

---

## 功能特点

- 从 DB Tree 中选择一个完整点云作为源点云 **A**。
- 从 DB Tree 中选择一个或多个点云实例，自动读取它们的 CloudCompare Bounding Box。
- 自动获取每个包围框的：
  - `Xmin / Xmax / Length X`
  - `Ymin / Ymax / Length Y`
  - `Zmin / Zmax / Length Z`
- 支持 `Ctrl` / `Shift` 一次选择多个包围框实例。
- 支持分多次继续添加包围框。
- 使用 CloudCompare `Unique ID` 去重，同一个实例不会重复加入。
- 自动阻止把源点云 A 本身作为删除包围框。
- 多个包围框按并集处理。
- 包围框边界上的点也视为框内点并删除。
- 生成新的结果点云，原始点云 A 不删除，仅自动隐藏。
- 使用 `ReferenceCloud + partialClone()` 生成结果，尽量保留原点云已有属性。

数学关系为：

```text
删除区域 = BBox1 ∪ BBox2 ∪ ... ∪ BBoxN

Result = A - 删除区域
```

---

## 适用场景

例如完整点云中存在车辆、设备、局部构件或其他需要整体剔除的区域，而普通 `Segmentation` 会沿当前视角贯穿选择区域，此时可以：

1. 准备若干用于表示删除区域的点云实例（可以使用 CloudCompare 自带的 'Cross Section' 工具提前把待删除区域裁剪出来）；
2. 使用这些实例各自的三维 Bounding Box 作为删除范围；
3. 一次性从完整点云 A 中删除所有这些 Bounding Box 内的点。

用于定义 Bounding Box 的点云实例本身不一定需要包含所有待删除点。插件只读取它们的 XYZ 最小值和最大值。

---

# 使用前准备

## 1. CloudCompare

推荐环境：

| 项目 | 要求 |
| --- | --- |
| CloudCompare | 2.13.x |
| 推荐版本 | 2.13.2（仅在此版本测试过） |
| 操作系统 | Windows 64-bit |
| Python 支持 | CloudCompare PythonRuntime 插件 |

CloudCompare 2.13.2 Windows Installer 提供 Python 插件安装选项。

官方下载：

- CloudCompare Releases: <https://www.cloudcompare.org/release/>

如果当前 CloudCompare 中完全看不到 Python / Python Plugin / Python Runtime 相关功能，建议重新运行 CloudCompare 安装程序，并确认已经安装 **Python plugin**。

CloudCompare PythonRuntime 项目及文档：

- <https://github.com/tmontaigu/CloudCompare-PythonRuntime>
- <https://tmontaigu.github.io/CloudCompare-PythonRuntime/getting_started.html>

> 对普通使用者而言，如果使用 CloudCompare 官方 Windows Installer 中提供的 PythonRuntime，一般不需要为了运行本插件再单独安装一套系统 Python。

---

## 2. 插件文件

运行插件至少需要以下两个文件：

```text
multi_box_remove.py
bbox_core.py
```

两个文件必须放在 **同一个目录**。

测试文件：

```text
test_bbox_core.py
```

只用于开发和单元测试，普通用户无需复制到 CloudCompare 插件目录。

推荐仓库结构：

```text
cloudcompare-multi-bbox-remove/
├── README.md
├── multi_box_remove.py
├── bbox_core.py
├── test_bbox_core.py
└── .gitignore
```

不要把下面这些运行缓存上传到 GitHub：

```text
__pycache__/
.pytest_cache/
*.pyc
```

---

## 3. 坐标条件

这是使用本插件最重要的前提之一。

**源点云 A 与所有用于定义 Bounding Box 的实例必须位于同一个 CloudCompare 坐标框架中。**

最推荐的情况是：

- 包围框实例直接从 A 中裁剪或复制得到；或者
- A 与包围框实例本来就来自同一套坐标系，并且在 CloudCompare 中保持一致的位置关系。

如果不同点云使用了不同的：

- Global Shift
- Global Scale
- 坐标原点
- 外部变换矩阵

则应先确认它们在 CloudCompare 中的实际 XYZ 坐标能够直接比较，否则包围框范围可能与 A 不一致。

---

# 安装插件

## 方法：Custom Python Plugins 目录

创建一个目录，例如：

```text
D:\CloudComparePythonPlugins
```

将以下文件复制进去：

```text
D:\CloudComparePythonPlugins\
├── multi_box_remove.py
└── bbox_core.py
```

然后在 CloudCompare 的 PythonRuntime / Python Plugin 设置中，将 **Custom plugins path** 指向：

```text
D:\CloudComparePythonPlugins
```

完全退出并重新启动 CloudCompare。

PythonRuntime 会在启动时扫描配置目录中的 Python 模块，并注册继承自 `pycc.PythonPluginInterface` 的插件。

重新启动后，在 Python Plugin Launcher 中查找本插件及其操作项。

---

# 使用方法

假设 DB Tree 中存在：

```text
PointCloud_A
BoxCloud_01
BoxCloud_02
BoxCloud_03
```

其中：

- `PointCloud_A`：需要进行删除操作的完整源点云；
- `BoxCloud_01 ~ 03`：用于提供删除范围 Bounding Box 的点云实例。

---

## 第 1 步：设置源点云 A

在 DB Tree 中 **只选中一个完整源点云**：

```text
PointCloud_A
```

执行：

```text
1 - 设置源点云 A
```

CloudCompare Console 会输出类似：

```text
[MultiBoxRemove] 已设置源点云 A: PointCloud_A [ID=12, points=5823412]
[MultiBoxRemove] 已清空旧包围框。
```

每次重新设置 A 时，之前已经保存的包围框列表都会被清空。

---

## 第 2 步：添加一个或多个包围框

在 DB Tree 中选择用于定义删除区域的点云实例。

Windows 下可以按住 `Ctrl` 一次选择多个：

```text
BoxCloud_01
BoxCloud_02
BoxCloud_03
```

然后执行：

```text
2 - 添加所选点云的包围框
```

插件会自动读取每个实例的 Bounding Box，并在 Console 输出：

```text
包围框 1: BoxCloud_01 [ID=21]
  X: [12.315000000, 18.426000000]  Length X = 6.111000000
  Y: [-3.210000000, 1.825000000]   Length Y = 5.035000000
  Z: [0.452000000, 3.916000000]    Length Z = 3.464000000
```

可以分多次继续添加其他实例。

如果重复选择同一个 DB Tree 实例，插件会根据 CloudCompare `Unique ID` 自动跳过。

---

## 第 3 步：检查当前包围框

执行：

```text
查看当前包围框
```

插件会在 Console 中重新打印全部 Bounding Box 的：

```text
Xmin / Xmax / Length X
Ymin / Ymax / Length Y
Zmin / Zmax / Length Z
```

建议第一次使用或处理重要数据时，在真正删除前先检查这些范围。

---

## 第 4 步：执行删除

确认所有包围框正确后，执行：

```text
3 - 删除所有包围框内点
```

插件对 A 中的每个点判断：

```text
xmin <= x <= xmax
ymin <= y <= ymax
zmin <= z <= zmax
```

如果某个点位于 **任意一个** Bounding Box 中，就会被排除。

最终生成新点云：

```text
<原点云名>_OUTSIDE_N_BBOXES
```

例如：

```text
PointCloud_A_OUTSIDE_3_BBOXES
```

原始 `PointCloud_A` 不会被删除，只会自动隐藏。

---

## 第 5 步：重新选择包围框

执行：

```text
清空全部包围框
```

只会清空当前保存的 Bounding Box 列表，不会清除已经设置的源点云 A。

之后可以重新选择其他 DB Tree 实例并继续添加。

---

# Bounding Box 定义

本插件使用的是 **Axis-Aligned Bounding Box（AABB，轴对齐包围框）**。

对于一个作为包围框来源的 CloudCompare 实体：

```text
X range = [Xmin, Xmax]
Y range = [Ymin, Ymax]
Z range = [Zmin, Zmax]
```

尺寸为：

```text
Length X = Xmax - Xmin
Length Y = Ymax - Ymin
Length Z = Zmax - Zmin
```

插件删除条件为：

```python
inside = (
    (x >= xmin) & (x <= xmax) &
    (y >= ymin) & (y <= ymax) &
    (z >= zmin) & (z <= zmax)
)
```

多个 Bounding Box：

```text
remove = inside_box_1 OR inside_box_2 OR ... OR inside_box_n
keep   = NOT remove
```

---

# AABB 与 OBB 的区别

当前版本使用 **AABB**，即包围框始终与 CloudCompare XYZ 坐标轴平行。

即使一个点云实例本身是倾斜的，插件读取的仍然是它在 XYZ 三个方向上的最小外包长方体。

当前版本 **不支持旋转包围框 OBB（Oriented Bounding Box）**。

因此：

```text
支持：XYZ 轴对齐 Bounding Box
不支持：任意角度旋转 Bounding Box
```

---

# 与 CloudCompare Segmentation 的区别

CloudCompare 常规 Segmentation 主要依据当前视图中的二维投影区域进行交互选择。因此当前后点云在屏幕上发生投影重叠时，可能会同时被包含在选择区域中。

本插件不使用屏幕投影，而是直接按照：

```text
X + Y + Z
```

三维范围判断点是否位于包围框内。

因此更适合需要明确限制三维深度范围的批量矩形区域删除任务。

---

# 性能说明

Bounding Box 空间判断使用 NumPy 向量化计算：

```text
Source points × Bounding boxes
```

通常 XYZ 判断本身速度较快。

为了尽量保留源点云已有的颜色、Scalar Fields 等 CloudCompare 属性，结果通过：

```text
ReferenceCloud
    ↓
partialClone()
    ↓
Result cloud
```

生成。

CloudCompare 2.13.x PythonRuntime 中，大规模索引加入 `ReferenceCloud` 的速度可能低于原生 C++ 实现。因此当源点云达到数千万点时，结果点云构建阶段可能成为主要性能瓶颈。

如果后续需要处理超大规模点云，可以考虑将核心逻辑迁移为原生 CloudCompare C++ 插件。

---

# 常见问题

## 1. CloudCompare 中找不到 Python Plugin Launcher

检查是否安装了 CloudCompare PythonRuntime。

对于 CloudCompare 2.13.2 Windows 版本，建议使用官方 Installer，并确认安装过程中已经选择 Python plugin。

---

## 2. 插件没有出现在 Python Plugin Launcher 中

检查：

1. `multi_box_remove.py` 和 `bbox_core.py` 是否位于同一目录；
2. PythonRuntime 的 Custom plugins path 是否指向该目录；
3. 修改路径后是否完全重启过 CloudCompare；
4. CloudCompare Console 中是否存在 Python 导入错误。

---

## 3. 提示找不到 `bbox_core`

确保目录结构是：

```text
D:\CloudComparePythonPlugins\
├── multi_box_remove.py
└── bbox_core.py
```

不要只复制 `multi_box_remove.py`。

---

## 4. 删除的位置不正确

优先检查：

- A 与 Bounding Box 实例是否在同一坐标系；
- 是否存在不同的 Global Shift / Scale；
- Console 打印的 `X/Y/Z range` 是否与预期一致；
- 是否误选了一个 Bounding Box 很大的实体。

建议在执行删除前先运行：

```text
查看当前包围框
```

---

## 5. 为什么倾斜目标周围删除了额外点？

因为当前版本使用的是 XYZ 轴对齐 AABB，而不是旋转 OBB。

对于倾斜点云，其 AABB 通常会比实际点云占据更大的空间，因此会包含目标周围的一部分额外区域。

---

## 6. 原始点云不见了

插件完成处理后会调用：

```text
source_cloud.setEnabled(False)
```

所以 A 只是被隐藏，并没有从 DB Tree 删除。

重新勾选/启用原始点云即可恢复显示。

---

# 开发与测试

核心 Bounding Box 运算被独立放在：

```text
bbox_core.py
```

因此可以脱离 CloudCompare GUI 测试基础几何逻辑。

开发环境需要：

```text
Python
NumPy
pytest
```

执行：

```bash
pytest -q
```

主要测试内容包括：

- 两个角点自动标准化为 `min/max`；
- Box dimensions 计算；
- 多个 Bounding Box 并集删除；
- Bounding Box 边界点删除；
- 同一 CloudCompare 实例重复添加时去重；
- 非法点数组尺寸检查。

> `pytest` 只用于开发测试，普通 CloudCompare 用户不需要安装它才能运行插件。

---

# 当前限制

- 目前主要针对 CloudCompare 2.13.x / 2.13.2 Windows 环境设计。
- 只支持 AABB，不支持 OBB。
- 当前包围框来源主要面向 DB Tree 中能够提供 `getBoundingBox()` 的实体，推荐直接使用点云实例。
- 超大规模点云在 `ReferenceCloud` 索引构造阶段可能较慢。
- 插件不会自动判断两个不同数据源的 Global Shift / Scale 是否具有可比性，使用前应自行确认坐标一致。

---

# 技术实现

主要使用 CloudCompare PythonRuntime API：

```text
pycc.GetInstance()
getSelectedEntities()
getUniqueID()
getBoundingBox()
points()
cccorelib.ReferenceCloud
partialClone()
addToDB()
```

其中：

- `getSelectedEntities()`：读取 DB Tree 当前选择项；
- `getUniqueID()`：识别 CloudCompare 实例并防止重复添加；
- `getBoundingBox()`：获取实体 XYZ Bounding Box；
- `points()`：访问源点云坐标；
- `ReferenceCloud + partialClone()`：根据保留点索引创建结果点云。

---

# 参考资料

- CloudCompare: <https://www.cloudcompare.org/>
- CloudCompare Downloads: <https://www.cloudcompare.org/release/>
- CloudCompare PythonRuntime: <https://github.com/tmontaigu/CloudCompare-PythonRuntime>
- PythonRuntime Getting Started: <https://tmontaigu.github.io/CloudCompare-PythonRuntime/getting_started.html>

---

# License

本仓库发布前建议明确选择并添加 `LICENSE` 文件。

如果希望代码可自由使用、修改和分发，可以根据项目需求选择 MIT、BSD-3-Clause、Apache-2.0 等开源许可证；请根据你实际希望授予的权利选择，不要仅在 README 中写许可证名称而不提交对应的 `LICENSE` 文件。
