/**
 * Custom hook for real-time document progress updates using Server-Sent Events (SSE)
 */

import { useState, useEffect, useRef } from "react";
import { ProcessingProgress } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface UseDocumentProgressReturn {
  progress: ProcessingProgress | null;
  isConnected: boolean;
  error: string | null;
}

/**
 * Hook to subscribe to real-time document progress updates via SSE
 *
 * @param documentId - The document ID to track (null to disable)
 * @returns Progress data, connection status, and error state
 */
export function useDocumentProgress(
  documentId: string | null
): UseDocumentProgressReturn {
  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Don't connect if no document ID
    if (!documentId) {
      return;
    }

    let eventSource: EventSource | null = null;
    const reconnectTimeout: NodeJS.Timeout | null = null;

    const connect = () => {
      try {
        // Create EventSource connection
        const url = `${API_BASE_URL}/api/documents/${documentId}/progress/stream`;
        eventSource = new EventSource(url);
        eventSourceRef.current = eventSource;

        // Connection opened
        eventSource.onopen = () => {
          console.log(`SSE connected for document ${documentId}`);
          setIsConnected(true);
          setError(null);
        };

        // Handle progress events
        eventSource.addEventListener("progress", (event) => {
          try {
            const data = JSON.parse(event.data);
            setProgress(data);
          } catch (err) {
            console.error("Failed to parse progress event:", err);
          }
        });

        // Handle chunk completed events
        eventSource.addEventListener("chunk_completed", (event) => {
          try {
            const data = JSON.parse(event.data);
            setProgress(data);
          } catch (err) {
            console.error("Failed to parse chunk_completed event:", err);
          }
        });

        // Handle completion event
        eventSource.addEventListener("completed", (event) => {
          try {
            const data = JSON.parse(event.data);
            setProgress(data);
            console.log(`Document ${documentId} processing completed`);

            // Close connection
            if (eventSource) {
              eventSource.close();
              setIsConnected(false);
            }
          } catch (err) {
            console.error("Failed to parse completed event:", err);
          }
        });

        // Handle error event from server
        eventSource.addEventListener("error", (event: Event) => {
          try {
            const messageEvent = event as MessageEvent;
            if (messageEvent.data) {
              const data = JSON.parse(messageEvent.data);
              setError(data.error_message || data.error || "Processing failed");
              console.error(`Document ${documentId} processing failed:`, data);
            }

            // Close connection
            if (eventSource) {
              eventSource.close();
              setIsConnected(false);
            }
          } catch (err) {
            console.error("Failed to parse error event:", err);
          }
        });

        // Handle connection errors
        eventSource.onerror = (err) => {
          console.error("SSE connection error:", err);
          setIsConnected(false);

          // Close the connection
          if (eventSource) {
            eventSource.close();
          }

          // Don't reconnect if we received a completion or error event
          // (connection will be closed gracefully)
          if (eventSource?.readyState === EventSource.CLOSED) {
            setError("Connection closed");
          }
        };
      } catch (err) {
        console.error("Failed to create SSE connection:", err);
        setError("Failed to connect to progress stream");
        setIsConnected(false);
      }
    };

    // Initial connection
    connect();

    // Cleanup function
    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (eventSource) {
        console.log(`Closing SSE connection for document ${documentId}`);
        eventSource.close();
        eventSourceRef.current = null;
      }
    };
  }, [documentId]);

  return { progress, isConnected, error };
}
