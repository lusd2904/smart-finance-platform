package influx

import (
	"strings"
	"testing"
)

// Official /api/v2/query annotated CSV: annotation names occupy column 0 on
// #datatype/#group/#default rows; the header and data rows start with an
// empty annotation column so headers are ",result,table,...".
const annotatedLeadingEmpty = `#datatype,string,long,dateTime:RFC3339,dateTime:RFC3339,dateTime:RFC3339,double,double,double,double,double,string,string
#group,false,false,true,true,false,false,false,false,false,false,true,true
#default,_result,,,,,,,,,,,
,result,table,_start,_stop,_time,open,high,low,close,volume,_measurement,symbol
,,0,2024-01-01T00:00:00Z,2024-09-01T00:00:00Z,2024-08-30T00:00:00Z,100,110,90,105,1000,daily_kline,AAPL
,,0,2024-01-01T00:00:00Z,2024-09-01T00:00:00Z,2024-08-31T00:00:00Z,105,115,100,112,1100,daily_kline,AAPL
`

// Some dialects put the annotation token in column 1 after a leading comma.
const annotatedLeadingEmptyAnnotations = `,#datatype,string,long,dateTime:RFC3339,double,string
,#group,false,false,false,false,true
,#default,_result,,,,
,result,table,_time,close,symbol
,,0,2024-08-30T00:00:00Z,105,AAPL
`

const plainHeaderAtZero = `result,table,_time,open,high,low,close,volume,symbol
_result,0,2024-08-30T00:00:00Z,100,110,90,105,1000,AAPL
`

func TestParseFluxCSVLeadingEmptyColumn(t *testing.T) {
	recs, err := parseFluxCSV([]byte(annotatedLeadingEmpty))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if len(recs) != 2 {
		t.Fatalf("got %d records, want 2 (header detection must accept result at col 1)", len(recs))
	}
	if recs[0]["symbol"] != "AAPL" {
		t.Fatalf("symbol=%q", recs[0]["symbol"])
	}
	if recs[0]["_time"] != "2024-08-30T00:00:00Z" {
		t.Fatalf("_time=%q", recs[0]["_time"])
	}
	if recs[0]["open"] != "100" || recs[0]["high"] != "110" || recs[0]["low"] != "90" || recs[0]["close"] != "105" || recs[0]["volume"] != "1000" {
		t.Fatalf("ohlcv mapped by header name: %v", recs[0])
	}
	if recs[1]["close"] != "112" || recs[1]["volume"] != "1100" {
		t.Fatalf("second row: %v", recs[1])
	}
	if _, ok := recs[0][""]; ok {
		t.Fatalf("empty leading column should not become a record key: %v", recs[0])
	}
}

func TestParseFluxCSVLeadingEmptyAnnotationToken(t *testing.T) {
	recs, err := parseFluxCSV([]byte(annotatedLeadingEmptyAnnotations))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if len(recs) != 1 {
		t.Fatalf("got %d records, want 1 after skipping # annotation rows", len(recs))
	}
	if recs[0]["symbol"] != "AAPL" || recs[0]["close"] != "105" {
		t.Fatalf("mapped: %v", recs[0])
	}
}

func TestParseFluxCSVHeaderResultAtIndexZero(t *testing.T) {
	recs, err := parseFluxCSV([]byte(plainHeaderAtZero))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if len(recs) != 1 {
		t.Fatalf("got %d records, want 1", len(recs))
	}
	if recs[0]["symbol"] != "AAPL" || recs[0]["close"] != "105" {
		t.Fatalf("mapped: %v", recs[0])
	}
}

func TestParseFluxCSVSkipsHashAnnotationRows(t *testing.T) {
	raw := strings.Join([]string{
		"#datatype,string,long,dateTime:RFC3339,string",
		"#group,false,false,false,true",
		"#default,_result,,,",
		"#comment,ignored",
		",result,table,_time,symbol",
		",,0,2024-08-30T00:00:00Z,AAPL",
		"#datatype,string,long,dateTime:RFC3339,string",
		",,0,2024-08-31T00:00:00Z,MSFT",
	}, "\n")
	recs, err := parseFluxCSV([]byte(raw))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if len(recs) != 2 {
		t.Fatalf("got %d records, want 2 (mid-stream # rows skipped)", len(recs))
	}
	if recs[0]["symbol"] != "AAPL" || recs[1]["symbol"] != "MSFT" {
		t.Fatalf("rows: %v", recs)
	}
}

func TestParseFluxCSVSkipsLongFormatRows(t *testing.T) {
	raw := `#datatype,string,long,dateTime:RFC3339,string,string
#default,_result,,,,
,result,table,_time,_field,_value
,,0,2024-08-30T00:00:00Z,close,105
`
	recs, err := parseFluxCSV([]byte(raw))
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	if len(recs) != 0 {
		t.Fatalf("got %d records, want 0 (unpivoted _field/_value rows skipped)", len(recs))
	}
}

func TestParseFluxCSVEmptyAndNoHeader(t *testing.T) {
	recs, err := parseFluxCSV(nil)
	if err != nil || recs != nil {
		t.Fatalf("empty: recs=%v err=%v", recs, err)
	}
	recs, err = parseFluxCSV([]byte("#datatype,string\n#group,false\n"))
	if err != nil || recs != nil {
		t.Fatalf("annotations only: recs=%v err=%v", recs, err)
	}
}

func TestFluxHeaderHasResultAnyColumn(t *testing.T) {
	if fluxHeaderHasResult([]string{"result", "table"}) != true {
		t.Fatal("result at col 0")
	}
	if fluxHeaderHasResult([]string{"", "result", "table"}) != true {
		t.Fatal("result at col 1")
	}
	if fluxHeaderHasResult([]string{"#datatype", "string"}) {
		t.Fatal("annotation is not a header")
	}
}

func TestFluxAnnotationRow(t *testing.T) {
	if !fluxAnnotationRow([]string{"#datatype", "string"}) {
		t.Fatal("#datatype at col 0")
	}
	if !fluxAnnotationRow([]string{"", "#group", "false"}) {
		t.Fatal("#group after leading empty")
	}
	if fluxAnnotationRow([]string{"", "result", "table"}) {
		t.Fatal("header is not an annotation")
	}
	if fluxAnnotationRow([]string{"", "", "0"}) {
		t.Fatal("data row with empty col 0 is not an annotation")
	}
}
