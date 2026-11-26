"""将站点打包成单个可转发的 HTML 文件（内联 CSS / 数据 / 脚本）。"""
import io
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    with io.open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return f.read()


def main():
    html = read("index.html")
    css = read(os.path.join("assets", "styles.css"))
    data = read(os.path.join("data", "data.js"))
    app = read(os.path.join("assets", "app.js"))
    xlsx = read(os.path.join("assets", "xlsx.full.min.js"))

    def js(s):
        return s.replace("</script", "<\\/script")

    html = html.replace('<script src="data/local_overrides.js"></script>\n', '')
    html = html.replace('<script src="http://127.0.0.1:8765/api/local-overrides.js"></script>\n', '')
    html = html.replace('<script src="api/local-overrides.js"></script>\n', '')
    html = html.replace(
        '<link rel="stylesheet" href="assets/styles.css">',
        "<style>\n" + css + "\n</style>",
    )
    html = html.replace(
        '<script src="assets/xlsx.full.min.js"></script>',
        "<script>\n" + js(xlsx) + "\n</script>",
    )
    html = html.replace(
        '<script src="data/data.js"></script>',
        "<script>\n" + js(data) + "\n</script>",
    )
    html = html.replace(
        '<script src="assets/app.js"></script>',
        "<script>\n" + js(app) + "\n</script>",
    )

    out = os.path.join(BASE, "产品项目管理-单文件版.html")
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成: " + out)
    print("大小: %.1f KB" % (len(html.encode("utf-8")) / 1024.0))


if __name__ == "__main__":
    main()
