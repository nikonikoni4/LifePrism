import { GoogleGenAI, Chat, GenerateContentResponse } from "@google/genai";

let aiClient: GoogleGenAI | null = null;
let chatSession: Chat | null = null;

const getClient = (): GoogleGenAI => {
  if (!aiClient) {
    // In a real scenario, we use process.env.API_KEY. 
    // We assume it is available as per instructions.
    const apiKey = process.env.API_KEY || ''; 
    aiClient = new GoogleGenAI({ apiKey });
  }
  return aiClient;
};

export const initializeChat = (): Chat => {
  const client = getClient();
  chatSession = client.chats.create({
    model: 'gemini-2.5-flash',
    config: {
      systemInstruction: "You are a helpful and motivating productivity assistant for a 'Quantified Self' dashboard. Keep responses concise, encouraging, and focused on data, goals, and improvement.",
    },
  });
  return chatSession;
};

export const sendMessageToGemini = async function* (message: string) {
  if (!chatSession) {
    initializeChat();
  }

  if (!chatSession) {
      throw new Error("Failed to initialize chat session");
  }

  try {
    const result = await chatSession.sendMessageStream({ message });
    
    for await (const chunk of result) {
        // Safe casting based on SDK usage
        const c = chunk as GenerateContentResponse;
        if (c.text) {
            yield c.text;
        }
    }
  } catch (error) {
    console.error("Gemini API Error:", error);
    yield "I'm having trouble connecting to my brain right now. Please check your network or API key configuration.";
  }
};