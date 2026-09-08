package captcha

import (
	"bytes"
	"encoding/base64"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"math/rand"
)

func Generate() (imgBase64 string, answer string, err error) {
	num1 := rand.Intn(10)
	num2 := rand.Intn(10)
	ops := []struct {
		op string
		fn func(a, b int) int
	}{
		{"+", func(a, b int) int { return a + b }},
		{"-", func(a, b int) int {
			if a < b {
				a, b = b, a
			}
			return a - b
		}},
		{"*", func(a, b int) int { return a * b }},
	}
	choice := ops[rand.Intn(len(ops))]
	if choice.op == "-" && num1 < num2 {
		num1, num2 = num2, num1
	}
	result := choice.fn(num1, num2)
	text := fmt.Sprintf("%d %s %d = ?", num1, choice.op, num2)

	img := image.NewRGBA(image.Rect(0, 0, 160, 60))
	bg := color.RGBA{R: 0xEA, G: 0xEA, B: 0xEA, A: 0xFF}
	for y := 0; y < 60; y++ {
		for x := 0; x < 160; x++ {
			img.Set(x, y, bg)
		}
	}
	drawSimpleText(img, text)

	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		return "", "", err
	}
	return base64.StdEncoding.EncodeToString(buf.Bytes()), fmt.Sprintf("%d", result), nil
}

func drawSimpleText(img *image.RGBA, text string) {
	blue := color.RGBA{R: 0, G: 0, B: 255, A: 255}
	x := 12
	for _, ch := range text {
		drawChar(img, ch, x, 18, blue)
		x += 10
	}
}

func drawChar(img *image.RGBA, ch rune, x, y int, c color.RGBA) {
	pattern, ok := charPatterns[ch]
	if !ok {
		return
	}
	for row, line := range pattern {
		for col, on := range line {
			if on == '1' {
				for dy := 0; dy < 2; dy++ {
					for dx := 0; dx < 2; dx++ {
						img.Set(x+col*2+dx, y+row*2+dy, c)
					}
				}
			}
		}
	}
}

var charPatterns = map[rune][]string{
	'0': {"0110", "1001", "1001", "1001", "0110"},
	'1': {"0010", "0110", "0010", "0010", "0111"},
	'2': {"0110", "1001", "0010", "0100", "1111"},
	'3': {"1110", "0001", "0110", "0001", "1110"},
	'4': {"1001", "1001", "1111", "0001", "0001"},
	'5': {"1111", "1000", "1110", "0001", "1110"},
	'6': {"0110", "1000", "1110", "1001", "0110"},
	'7': {"1111", "0001", "0010", "0100", "0100"},
	'8': {"0110", "1001", "0110", "1001", "0110"},
	'9': {"0110", "1001", "0111", "0001", "0110"},
	'+': {"0000", "0100", "1110", "0100", "0000"},
	'-': {"0000", "0000", "1110", "0000", "0000"},
	'*': {"0000", "1010", "0110", "1010", "0000"},
	'=': {"0000", "1111", "0000", "1111", "0000"},
	'?': {"0110", "1001", "0010", "0010", "0010"},
	' ': {"0000", "0000", "0000", "0000", "0000"},
}
