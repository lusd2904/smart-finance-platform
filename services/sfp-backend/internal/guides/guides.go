package guides

import (
	"embed"
	"fmt"
	"strings"
)

//go:embed resources/*.md
var files embed.FS

var titles = map[string]string{
	"market": "行情中心使用说明", "quant": "量化交易使用说明", "trade": "交易中心使用说明",
	"sentiment": "舆情分析使用说明", "ai": "AI 管理使用说明", "analysis": "任务中心使用说明",
}

func Load(module string) (map[string]string, error) {
	if titles[module] == "" {
		return nil, fmt.Errorf("unknown module")
	}
	raw, err := files.ReadFile("resources/" + module + ".md")
	if err != nil {
		return nil, err
	}
	markdown := string(raw)
	return map[string]string{
		"module":   module,
		"title":    guideTitle(markdown, titles[module]),
		"markdown": markdown,
	}, nil
}

func guideTitle(markdown, fallback string) string {
	for _, line := range strings.Split(markdown, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "# ") {
			title := strings.TrimSpace(strings.TrimPrefix(line, "# "))
			if title != "" {
				return title
			}
		}
	}
	return fallback
}
