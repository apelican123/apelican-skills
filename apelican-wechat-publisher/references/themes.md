# 三套模板怎么选

公众号正文最终要在手机窄栏里读完。港式印刷品（书刊、报纸副刊、新闻版）好看的地方通常不是花纹，而是：

- 标题比内地营销号克制，不拿色块胶囊当二级标题
- 行距明显大于字号，段与段之间有呼吸
- 颜色很少，一种强调色就够
- 引语靠左边一条细线，而不是大色块
- 对齐简单，左对齐为主

三套 CSS 都写给 wenyan：根选择器是 `#wenyan`。使用时把 CSS 路径传给 `-c`，不必先 `wenyan theme --add`。

## 人文纸墨 `templates/humanities.css`

适合随笔、书评、城市笔记、文化评论。

- 标题用宋体，正文用系统黑体，行距约 2.0
- 墨色正文、暗红强调，不要亮蓝
- 一级标题不大吼，二级标题用下边线而不是实心底
- 引用像印刷品的摘句

配套骨架：`templates/humanities.md`  
代码高亮：`github` 或 `solarized-light`

```bash
wenyan publish -f article.md -c templates/humanities.css -h github --env-file=.env
```

## 科技青简 `templates/tech.css`

适合教程、产品说明、技术笔记。

- 全程无衬线，行距约 1.8
- 强调色用冷静的蓝，不强行 Mac 窗口装饰
- 二级标题左侧一条竖线
- 行内代码和代码块背景分开，表格要能在手机里换行

配套骨架：`templates/tech.md`  
代码高亮：`solarized-light` 或 `github`

若你讨厌代码块的红黄绿圆点，加上 `--no-mac-style`。

```bash
wenyan publish -f article.md -c templates/tech.css -h solarized-light --no-mac-style --env-file=.env
```

## 社会热点港闻 `templates/social.css`

适合时评、热点综述、公共议题。

- 标题更重、更黑，左对齐
- 强调色用克制的朱红，只用在少量词和引语竖线
- 开头导语略小、略灰，像报纸 dek
- 段落更短，方便扫读

配套骨架：`templates/social.md`  
代码高亮：一般用不到；若有图表说明可用 `github`

```bash
wenyan publish -f article.md -c templates/social.css -h github --env-file=.env
```

## 和内置主题的关系

wenyan 自己还有 `default`、`lapis`、`phycat`。`lapis` 的二级标题是蓝底白字胶囊，更像常见技术博客，不像港刊。本技能默认走三套自定义 CSS；只有用户明确要内置主题时才用 `-t lapis`。

不要把三套 CSS 混进同一篇。一篇只用一个 `-c`。

## 封面

图文封面按 2.35:1 做，推荐 900×383。列表小图会变成 1:1，所以标题和关键物放在画面中心。出图规则见 [image-direction.md](image-direction.md)：先生图，退路才是 HTML 卡。不要把完整标题画进封面。
