---
name: wrongbook
description: 识别试卷图片中老师批改的错题（红叉/红圈/红色批注），提取结构化数据并生成纯练习版 PDF；同时把错题持久化到本地错题库，可按学科/时间区间出复习练习。覆盖小学/初中数学、语文（含古诗文）、英语、理化生（含图表）。关键词：错题整理、错题本、试卷批改、练习题、订正、复习。
when_to_use: 用户给出试卷图片要整理错题，或要求从历史错题里挑题做练习时触发。例如"帮我整理这张试卷的错题"、"把这周的数学错题做成练习"、"从错题本里随机抽 10 题出 PDF"。
allowed-tools: Read Bash(python3 *) Write
---

# wrongbook — 错题整理与练习 PDF 生成

本 skill 提供两条工作流：

- **A. 整理新试卷**：用户给一张或多张试卷图片 → 抽取错题 → 入库 + 生成练习 PDF
- **B. 从错题库出题**：用户口头描述条件（学科、时间、数量）→ 查库 → 生成练习 PDF

## 工作流 A：整理新试卷

按以下步骤执行，**不要**跳步、不要让用户手动写 JSON。

### A1：读取图片

用 `Read` 工具读取用户提供的每一张试卷图片（PNG/JPG/HEIC 等）。

**多图处理**：
- 如果用户一次给多张图，逐张读取
- 如果多张图属同一份试卷（继续页）：合并到**同一个 session JSON**，按页面顺序排错题
- 如果多张图属不同试卷/不同学科：默认仍合并为一个 session（学科分章节由 PDF 自动处理）；除非用户明说要分开

### A2：定位错题

逐张图判断哪些题被老师标错。判错信号（按可信度从高到低）：

- **红叉 ✗ / ✘ / × 直接打在题目或答案上**：高可信，必为错题
- **红圈圈住答案**：高可信
- **红色扣分（如 -2、-3）写在题号附近**：高可信
- **红色批注/横线划过学生作答**：中可信，结合上下文判断
- **题号前画红色对勾 ✓**：通常表示对，**不算错题**

打勾若为蓝色/黑色非批改痕迹要忽略。看不清时倾向于不收录，避免误收。

### A3：提取结构化数据

为每道错题构造一个 JSON 对象：

```json
{
  "id": 1,
  "source_qid": "8",
  "subject": "数学",
  "type": "计算题",
  "content": "题干完整文本（不含原题号）",
  "student_answer": "（可选）学生写的答案，便于后续复盘",
  "answer_lines": 3
}
```

**字段规则**：
- `id`：在本次输出 JSON 中**重新从 1 开始**编号，PDF 用这个题号
- `source_qid`：可选字符串。试卷原题号（如 `"8"`、`"15"`、`"二·3"`），用于学生对照原卷复盘。脚本目前不在 PDF 上显示，只入库
- `subject`：从 {数学, 语文, 英语, 物理, 化学, 生物, 政治, 历史, 地理, 其他} 中选一个；从试卷标题/题目内容判断
- `type`：题型，常见值：选择题、填空题、计算题、应用题、解答题、判断题、默写、翻译、阅读理解、作文。无法判定时填"未分类"
- `content`：完整题干，**不要包含原题号前缀**（如 `"8."` 这种要去掉）。**保留题干内的换行用 `\n`**。**选择题/判断题的选项必须每个选项一行**（用 `\n` 分隔，PDF 渲染会把连续空格压成 1 个）。数学公式用纯文本表达（如 `3/4 + 5/6`、`x^2 + 2x = 8`），目前**不做** LaTeX 渲染
- `student_answer`：可选。学生原作答，用于后续错题本，不会出现在练习版 PDF 上
- `answer_lines`：根据题型估算空白作答行数：
  - 选择题/判断题/填空题（短）：1
  - 填空题（长）/简答：2-3
  - 计算题：3-5
  - 应用题/解答题：5-8
  - 默写/作文：8-12

### A4：组装总 JSON

```json
{
  "title": "{学科}错题练习 · {YYYY-MM-DD}",
  "student": "（可选，用户提到才填）",
  "questions": [ ... ]
}
```

`title` 默认用今天的日期（看系统提供的 currentDate）。多学科混合时学科部分写"综合"。

### A5：写 JSON 并生成 PDF

把 JSON 用 `Write` 工具写到 `output/` 目录下（路径相对**当前工作目录**，**不是** skill 目录），文件名带时间戳：

```
output/wrongbook_<YYYYMMDD_HHMMSS>.json
output/wrongbook_<YYYYMMDD_HHMMSS>.pdf
```

如果当前工作目录下没有 `output/`，**直接** `Write` 创建即可（Write 会自动建父目录）。

然后调脚本生成 PDF：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_pdf.py <input.json> <output.pdf>
```

### A6：入库

把 session JSON 也入到本地错题库（同一个 `output/sessions/` 目录下，每个 session 一个文件）：

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/store.py add <input.json>
```

**默认 store dir = `./output/sessions/`**（项目本地、跟 PDF 同一棵树，方便备份/同步）。如需自定义可加 `--store-dir <path>`。

入库失败不影响 PDF 已经生成的结果，但要在汇报里告知用户。

### A7：汇报结果

简短告诉用户：
- 找到几道错题
- 各学科分布（如适用）
- JSON 与 PDF 路径
- 入库的 session id（store.py 输出会带）
- 哪些题不确定是否为错题（如有，列出供用户裁决）

---

## 工作流 B：从错题库出题

用户口头描述条件，例子：
- "把这周的数学错题做成练习"
- "从错题本里随机抽 10 道应用题"
- "把上个月所有错题打印出来"
- "session 20260512_143019 的题再做一遍"

### B1：解析条件

把口语条件映射到 `store.py query` 的参数：

| 用户说的 | 参数 |
| --- | --- |
| 这周/最近 7 天 | `--last-days 7` |
| 这个月/最近 30 天 | `--last-days 30` |
| 上个月、3 月份等具体月份 | `--since YYYY-MM-01 --until YYYY-MM-31` |
| 数学/语文/英语 | `--subject 数学` |
| 应用题/选择题等题型 | `--type 应用题` |
| 随机 N 道 | `--random --limit N` |
| 某个 session | `--session-id <sid>` |
| 自定义标题 | `--title "标题"` |
| 自定义学生名 | `--student "小明"` |

### B2：查询并写出 PDF

两步组合：

```bash
# 1) 查库 → 写 JSON
python3 ${CLAUDE_SKILL_DIR}/scripts/store.py query \
  --subject 数学 --last-days 7 \
  --title "本周数学错题复习" \
  --output output/practice_<YYYYMMDD_HHMMSS>.json

# 2) JSON → PDF
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_pdf.py \
  output/practice_<YYYYMMDD_HHMMSS>.json \
  output/practice_<YYYYMMDD_HHMMSS>.pdf
```

### B3：汇报

告诉用户：选出几道、PDF 路径。如果命中数量为 0，提示用户放宽条件并跑 `store.py stats` / `list-sessions` 让用户看库里有什么。

---

## 工具命令速查

```bash
# 看库统计
python3 ${CLAUDE_SKILL_DIR}/scripts/store.py stats

# 列最近 session
python3 ${CLAUDE_SKILL_DIR}/scripts/store.py list-sessions

# 查询全部参数
python3 ${CLAUDE_SKILL_DIR}/scripts/store.py query --help
```

---

## 边界与例外

- **页眉/总分/分数等不算判错信号**：试卷顶部"得分：80"、"满分 100"、"扣分汇总"等红字是统计信息，不是判错标记，**不要**收录为错题
- **图片质量差/看不清红色标记**：先告诉用户哪几题不确定，让用户口头确认或重拍，**不要**乱猜
- **图中有图表/几何图/化学方程式**：先用文字描述题干（"如图，△ABC 中 ..."），后续版本会支持裁原图嵌入
- **整张试卷没有红色标记**：询问用户是否提供了正确的图片，或是否要走"提供标准答案对比"的另一种模式（暂未实现）
- **错题超过 20 道**：先生成 PDF，并提示用户题量较大可考虑分册
- **多图属不同试卷且学科差异大**：默认合并入一个 session 并由 PDF 自动按学科分章；若用户明确要分开，分别走 A 流程

## 详细示例

完整的"图片 → JSON"抽取示例（含数学/语文/英语三个学科的样本）：

```
${CLAUDE_SKILL_DIR}/examples/extraction_guide.md
```

样例输入与样例输出 PDF：
- `${CLAUDE_SKILL_DIR}/examples/sample_input.json`
- 运行 `python3 ${CLAUDE_SKILL_DIR}/scripts/generate_pdf.py` 即可复现

## 当前未实现 / 待规划

- 数学公式 LaTeX 渲染（目前用纯文本表达）
- 图表/几何图自动裁剪嵌入 PDF
- 同类题拓展（基于错题让模型出 N 道相似题）
- 错题练习历史追踪（哪些已重做、还要再练）
