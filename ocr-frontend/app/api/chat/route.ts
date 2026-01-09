import { NextRequest, NextResponse } from "next/server";
import { FINANCIAL_UNDERWRITING_SYSTEM_PROMPT } from "@/data/financialPrompt";

const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const GEMINI_API_URL = process.env.GEMINI_API_URL || "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent";

/**
 * Chat message from frontend
 */
interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/**
 * Gemini API content format
 */
interface GeminiContent {
  role: "user" | "model";
  parts: { text: string }[];
}

/**
 * Format conversation history for Gemini API
 * Injects system prompt on first message to establish Financial AI persona
 */
function formatMessagesForGemini(
  messages: ChatMessage[],
  currentPrompt: string
): GeminiContent[] {
  const contents: GeminiContent[] = [];

  if (messages.length === 0) {
    // New conversation - system prompt + user's first message
    contents.push({
      role: "user",
      parts: [
        {
          text: `${FINANCIAL_UNDERWRITING_SYSTEM_PROMPT}\n\n---\n\nUser: ${currentPrompt}`,
        },
      ],
    });
  } else {
    // Continuing conversation - include history
    messages.forEach((msg, index) => {
      if (index === 0 && msg.role === "user") {
        // First user message includes system prompt
        contents.push({
          role: "user",
          parts: [
            {
              text: `${FINANCIAL_UNDERWRITING_SYSTEM_PROMPT}\n\n---\n\nUser: ${msg.content}`,
            },
          ],
        });
      } else {
        contents.push({
          role: msg.role === "user" ? "user" : "model",
          parts: [{ text: msg.content }],
        });
      }
    });

    // Add current prompt
    contents.push({
      role: "user",
      parts: [{ text: currentPrompt }],
    });
  }

  return contents;
}

/**
 * POST /api/chat
 *
 * Handles chat requests to Financial Underwriting AI powered by Gemini.
 * The AI has expertise in commercial real estate underwriting and financial analysis.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { messages, prompt } = body;

    // Validate request
    if (!prompt || typeof prompt !== "string") {
      return NextResponse.json(
        { error: "Invalid request: prompt is required" },
        { status: 400 }
      );
    }

    // Check for API key
    if (!GEMINI_API_KEY) {
      return NextResponse.json(
        { error: "GEMINI_API_KEY is not configured" },
        { status: 500 }
      );
    }

    // Format conversation for Gemini API
    const contents = formatMessagesForGemini(messages || [], prompt);

    // Call Gemini API
    const response = await fetch(`${GEMINI_API_URL}?key=${GEMINI_API_KEY}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        contents: contents,
        generationConfig: {
          temperature: 0.7, // Balanced for financial analysis
          maxOutputTokens: 8192,
          topP: 0.95,
          topK: 40,
        },
        safetySettings: [
          {
            category: "HARM_CATEGORY_HARASSMENT",
            threshold: "BLOCK_MEDIUM_AND_ABOVE",
          },
          {
            category: "HARM_CATEGORY_HATE_SPEECH",
            threshold: "BLOCK_MEDIUM_AND_ABOVE",
          },
          {
            category: "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold: "BLOCK_MEDIUM_AND_ABOVE",
          },
          {
            category: "HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold: "BLOCK_MEDIUM_AND_ABOVE",
          },
        ],
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error("Gemini API Error:", errorData);
      return NextResponse.json(
        { error: "Failed to get response from AI", details: errorData },
        { status: response.status }
      );
    }

    const data = await response.json();

    // Extract the text response from Gemini format
    const aiResponse =
      data.candidates?.[0]?.content?.parts?.[0]?.text ||
      "I apologize, but I couldn't generate a response. Please try again.";

    return NextResponse.json({
      response: aiResponse,
    });
  } catch (error) {
    console.error("Chat API Error:", error);
    return NextResponse.json(
      {
        error: "An error occurred while processing your request",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
