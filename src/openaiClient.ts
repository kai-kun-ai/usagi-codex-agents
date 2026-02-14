import OpenAI from 'openai';

export function getOpenAIClient() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY が未設定です。例: export OPENAI_API_KEY=...');
  }
  return new OpenAI({ apiKey });
}
