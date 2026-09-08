package handlers

import (
	"net/http"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/response"
)

func (s *Server) DictDataByType(w http.ResponseWriter, r *http.Request) {
	dictType := strings.TrimPrefix(r.URL.Path, "/system/dict/data/type/")
	dictType = strings.Trim(dictType, "/")
	if dictType == "" {
		response.Error(w, "字典类型不能为空")
		return
	}
	rows, err := s.DB.ListDictDataByType(r.Context(), dictType)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, rows)
}

func (s *Server) ConfigByKey(w http.ResponseWriter, r *http.Request) {
	configKey := strings.TrimPrefix(r.URL.Path, "/system/config/configKey/")
	configKey = strings.Trim(configKey, "/")
	if configKey == "" {
		response.Error(w, "参数键不能为空")
		return
	}
	value, err := s.DB.GetConfigValue(r.Context(), configKey)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	if value == "" {
		if cached, err := s.Redis.Get(r.Context(), "sys_config:"+configKey).Result(); err == nil {
			value = cached
		}
	}
	response.SuccessMsg(w, value)
}
