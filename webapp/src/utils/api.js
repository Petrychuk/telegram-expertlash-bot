// webapp/src/utils/api.js
export const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  const headers = {
    'Content-Type': 'application/json',
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  return headers;
};

export const apiRequest = async (url, options = {}) => {
  const defaultOptions = {
    headers: getAuthHeaders(),
    credentials: 'include',
  };
  
  const response = await fetch(url, { ...defaultOptions, ...options });
  
  // Обработка ошибок авторизации
  if (response.status === 401) {
    localStorage.removeItem('auth_token');
    // Редирект на homepage (главную страницу)
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
    throw new Error('Unauthorized');
  }
  
  return response;
};