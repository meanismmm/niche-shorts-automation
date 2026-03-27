// API 키 설정 파일
// 이 파일은 브라우저 로컬스토리지에 저장됩니다
// GitHub에 실제 키값을 올리지 마세요
const CONFIG = {
  get: (key) => localStorage.getItem(key) || '',
  set: (key, value) => localStorage.setItem(key, value),
  isReady: () => {
    return !!(
      localStorage.getItem('claude_api_key') &&
      localStorage.getItem('gemini_api_key') &&
      localStorage.getItem('pexels_api_key') &&
      localStorage.getItem('google_cloud_api_key') &&
      localStorage.getItem('pixabay_api_key')
    );
  },
  KEYS: {
    CLAUDE:       'claude_api_key',
    GEMINI:       'gemini_api_key',
    PEXELS:       'pexels_api_key',
    GOOGLE_CLOUD: 'google_cloud_api_key',
    PIXABAY:      'pixabay_api_key',
  }
};
