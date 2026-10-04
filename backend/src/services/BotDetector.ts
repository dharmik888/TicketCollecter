export interface BehaviorData {
  mouse_movements: number;
  keystrokes: number;
  scroll_events: number;
  session_duration_ms: number;
  events?: any[];
}

export class BotDetector {
  // Fix ML Server Bottleneck: Cache recent scores to prevent spamming the FastAPI server
  private static scoreCache = new Map<string, { score: number, timestamp: number }>();

  /**
   * Analyzes client behavior data to determine the likelihood of it being a bot.
   * Calls the ML integration API running at localhost:8000.
   * Returns a score between 0.0 (Human) and 1.0 (Definite Bot).
   */
  static async analyzeBehavior(userId: string, data: BehaviorData): Promise<number> {
    const cached = this.scoreCache.get(userId);
    // Only call the ML server once every 10 seconds per user
    if (cached && Date.now() - cached.timestamp < 10000) {
      return cached.score;
    }

    try {
      const response = await fetch('http://127.0.0.1:8000/predict-risk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: userId,
          user_id: userId,
          drop_id: 'default_drop',
          behavior_features: {
            mouse_events: data.mouse_movements || 0,
            keyboard_events: data.keystrokes || 0,
            scroll_events: data.scroll_events || 0,
            session_duration_ms: data.session_duration_ms || 0
          },
          events: data.events || [],
          rule_signals: {},
          risk_history: []
        })
      });

      if (!response.ok) {
        throw new Error(`ML API error: ${response.statusText}`);
      }

      const result = await response.json();
      const score = result.final_risk_score || 0.0;
      this.scoreCache.set(userId, { score, timestamp: Date.now() });
      return score;
    } catch (err) {
      console.error('Error calling ML Bot Detector API. Falling back to heuristics:', err);
      const score = this.heuristicFallback(data);
      this.scoreCache.set(userId, { score, timestamp: Date.now() });
      return score;
    }
  }

  static heuristicFallback(data: BehaviorData): number {
    let score = 0.0;
    if (data.session_duration_ms < 500 && data.mouse_movements === 0) {
      score += 0.5;
    }
    if (data.mouse_movements === 0 && data.scroll_events === 0) {
      score += 0.3;
    }
    const durationSeconds = (data.session_duration_ms / 1000) || 1;
    const actionsPerSecond = (data.mouse_movements + data.keystrokes + data.scroll_events) / durationSeconds;
    if (actionsPerSecond > 60) {
      score += 0.6;
    }
    if (data.keystrokes > 0 && data.session_duration_ms < 100) {
      score += 0.4;
    }
    return Math.min(Math.max(score, 0.0), 1.0);
  }
}
