// API 키 설정 파일
// 이 파일은 브라우저 로컬스토리지에 저장됩니다
// GitHub에 실제 키값을 올리지 마세요

const CONFIG = {
  // 저장된 키를 불러오는 함수
  get: (key) => localStorage.getItem(key) || '',

  // 키를 저장하는 함수
  set: (key, value) => localStorage.setItem(key, value),

  // 모든 키가 설정됐는지 확인
  isReady: () => {
    return !!(
      localStorage.getItem('claude_api_key') &&
      localStorage.getItem('gemini_api_key') &&
      localStorage.getItem('pexels_api_key') &&
      localStorage.getItem('google_cloud_api_key')
    );
  },

  // 키 목록
  KEYS: {
    CLAUDE:       'claude_api_key',
    GEMINI:       'gemini_api_key',
    PEXELS:       'pexels_api_key',
    GOOGLE_CLOUD: 'google_cloud_api_key',
  }
};
