package newscollect

import (
	"encoding/json"
	"encoding/xml"
	"strings"
)

func parseEastmoney(body []byte) []Item {
	var payload struct {
		Data struct {
			FastNewsList []struct {
				Title    string `json:"title"`
				Summary  string `json:"summary"`
				Content  string `json:"content"`
				ShowTime string `json:"showTime"`
				Code     string `json:"code"`
			} `json:"fastNewsList"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil
	}
	out := make([]Item, 0, len(payload.Data.FastNewsList))
	for _, raw := range payload.Data.FastNewsList {
		title := StripHTML(firstNonEmpty(raw.Title, raw.Summary))
		if title == "" {
			continue
		}
		content := StripHTML(firstNonEmpty(raw.Summary, raw.Content, title))
		code := strings.TrimSpace(raw.Code)
		url := ""
		if code != "" {
			url = "https://finance.eastmoney.com/a/" + code + ".html"
		}
		out = append(out, Item{
			Source:   "eastmoney",
			Title:    Truncate(title, titleMax),
			Content:  Truncate(content, contentMax),
			URL:      url,
			PubTime:  ParseTime(raw.ShowTime),
			UniqHash: MakeHash("eastmoney", title),
		})
	}
	return out
}

func parseSina(body []byte) []Item {
	var payload struct {
		Result struct {
			Data struct {
				Feed struct {
					List []struct {
						RichText   string `json:"rich_text"`
						CreateTime string `json:"create_time"`
						Ext        string `json:"ext"`
						DocURL     string `json:"docurl"`
					} `json:"list"`
				} `json:"feed"`
			} `json:"data"`
		} `json:"result"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil
	}
	list := payload.Result.Data.Feed.List
	out := make([]Item, 0, len(list))
	for _, raw := range list {
		title := StripHTML(raw.RichText)
		if title == "" {
			continue
		}
		docurl := strings.TrimSpace(raw.DocURL)
		if docurl == "" && raw.Ext != "" {
			var ext map[string]any
			if err := json.Unmarshal([]byte(raw.Ext), &ext); err == nil {
				docurl = asString(ext["docurl"])
			}
		}
		out = append(out, Item{
			Source:   "sina",
			Title:    Truncate(title, titleMax),
			Content:  Truncate(title, contentMax),
			URL:      docurl,
			PubTime:  ParseTime(raw.CreateTime),
			UniqHash: MakeHash("sina", title),
		})
	}
	return out
}

func parseTHS(body []byte) []Item {
	var payload struct {
		Data struct {
			List []struct {
				ID       any    `json:"id"`
				Title    string `json:"title"`
				Digest   string `json:"digest"`
				Content  string `json:"content"`
				URL      string `json:"url"`
				ShareURL string `json:"shareUrl"`
				Ctime    any    `json:"ctime"`
				Rtime    any    `json:"rtime"`
				Time     any    `json:"time"`
			} `json:"list"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil
	}
	out := make([]Item, 0, len(payload.Data.List))
	for _, raw := range payload.Data.List {
		title := StripHTML(raw.Title)
		if title == "" {
			continue
		}
		content := StripHTML(firstNonEmpty(raw.Digest, raw.Content, title))
		link := firstNonEmpty(raw.URL, raw.ShareURL)
		if strings.HasPrefix(link, "https:/") && !strings.HasPrefix(link, "https://") {
			link = strings.Replace(link, "https:/", "https://", 1)
		}
		ctime := raw.Ctime
		if ctime == nil || asString(ctime) == "" {
			ctime = raw.Rtime
		}
		if ctime == nil || asString(ctime) == "" {
			ctime = raw.Time
		}
		id := asString(raw.ID)
		if id == "" {
			id = title
		}
		out = append(out, Item{
			Source:   "ths",
			Title:    Truncate(title, titleMax),
			Content:  Truncate(content, contentMax),
			URL:      link,
			PubTime:  ParseTime(ctime),
			UniqHash: MakeHash("ths", id),
		})
	}
	return out
}

func parseWallstreetCN(body []byte) []Item {
	var payload struct {
		Data struct {
			Items []struct {
				ID          any    `json:"id"`
				Title       string `json:"title"`
				ContentText string `json:"content_text"`
				Content     any    `json:"content"`
				URI         string `json:"uri"`
				URL         string `json:"url"`
				DisplayTime any    `json:"display_time"`
				CreatedAt   any    `json:"created_at"`
				Score       any    `json:"score"`
			} `json:"items"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil
	}
	out := make([]Item, 0, len(payload.Data.Items))
	for _, raw := range payload.Data.Items {
		content := StripHTML(raw.ContentText)
		if content == "" {
			content = StripHTML(contentFromAny(raw.Content))
		}
		title := StripHTML(raw.Title)
		if title == "" {
			title = Truncate(content, 80)
		}
		if title == "" && content == "" {
			continue
		}
		if title == "" {
			title = Truncate(content, 80)
		}
		uri := firstNonEmpty(raw.URI, raw.URL)
		if uri != "" && !strings.HasPrefix(uri, "http") {
			uri = "https://wallstreetcn.com" + uri
		}
		ts := raw.DisplayTime
		if ts == nil || asString(ts) == "" {
			ts = raw.CreatedAt
		}
		if ts == nil || asString(ts) == "" {
			ts = raw.Score
		}
		id := asString(raw.ID)
		if id == "" {
			id = title
		}
		out = append(out, Item{
			Source:   "wallstreetcn",
			Title:    Truncate(title, titleMax),
			Content:  Truncate(firstNonEmpty(content, title), contentMax),
			URL:      uri,
			PubTime:  ParseTime(ts),
			UniqHash: MakeHash("wallstreetcn", id),
		})
	}
	return out
}

func parseJin10(body []byte) []Item {
	var payload struct {
		Data []struct {
			ID   any `json:"id"`
			Time any `json:"time"`
			Data any `json:"data"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil
	}
	out := make([]Item, 0, len(payload.Data))
	for _, raw := range payload.Data {
		inner, _ := raw.Data.(map[string]any)
		if inner == nil {
			continue
		}
		content := StripHTML(firstNonEmpty(asString(inner["content"]), asString(inner["title"])))
		title := StripHTML(firstNonEmpty(asString(inner["title"]), Truncate(content, 80)))
		if title == "" && content == "" {
			continue
		}
		if title == "" {
			title = Truncate(content, 80)
		}
		id := asString(raw.ID)
		if id == "" {
			id = title
		}
		out = append(out, Item{
			Source:   "jin10",
			Title:    Truncate(title, titleMax),
			Content:  Truncate(firstNonEmpty(content, title), contentMax),
			URL:      "https://www.jin10.com/",
			PubTime:  ParseTime(raw.Time),
			UniqHash: MakeHash("jin10", id),
		})
	}
	return out
}

func parseGoogleNewsRSS(body []byte, limit int) []Item {
	if limit <= 0 {
		limit = 10
	}
	var channel struct {
		Items []struct {
			Title       string `xml:"title"`
			Description string `xml:"description"`
			Link        string `xml:"link"`
			PubDate     string `xml:"pubDate"`
		} `xml:"channel>item"`
	}
	if err := xml.Unmarshal(body, &channel); err != nil {
		return nil
	}
	out := make([]Item, 0, limit)
	for i, raw := range channel.Items {
		if i >= limit {
			break
		}
		title := StripHTML(raw.Title)
		if title == "" {
			continue
		}
		summary := StripHTML(raw.Description)
		if summary == "" {
			summary = title
		}
		out = append(out, Item{
			Source:   "google_news",
			Title:    Truncate(title, titleMax),
			Content:  Truncate(summary, contentMax),
			URL:      strings.TrimSpace(raw.Link),
			PubTime:  ParseTime(raw.PubDate),
			UniqHash: MakeHash("google_news", title),
		})
	}
	return out
}

func contentFromAny(v any) string {
	switch t := v.(type) {
	case string:
		return t
	case map[string]any:
		return firstNonEmpty(asString(t["text"]), asString(t["content"]))
	default:
		return asString(v)
	}
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		v = strings.TrimSpace(v)
		if v != "" {
			return v
		}
	}
	return ""
}
