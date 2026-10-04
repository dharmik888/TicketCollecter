export interface BehaviorData {
  mouse_movements: number;
  keystrokes: number;
  scroll_events: number;
  session_duration_ms: number;
}

export class BotDetector {
  /**
   * Analyzes client behavior data to determine the likelihood of it being a bot.
   * Returns a score between 0.0 (Human) and 1.0 (Definite Bot).
   */
  static analyzeBehavior(data: BehaviorData): number {
    let score = 0.0;

    // Fast session with no interactions is highly suspicious
    if (data.session_duration_ms < 500 && data.mouse_movements === 0) {
      score += 0.5;
    }

    // No mouse movements and no scrolling is quite suspicious for web clients
    if (data.mouse_movements === 0 && data.scroll_events === 0) {
      score += 0.3;
    }

    // Extremely fast, dense interactions are characteristic of poorly rate-limited scripts
    const durationSeconds = (data.session_duration_ms / 1000) || 1; // Prevent div by 0
    const actionsPerSecond = (data.mouse_movements + data.keystrokes + data.scroll_events) / durationSeconds;
    
    if (actionsPerSecond > 60) {
      score += 0.6; // Humans generally don't trigger 60 discrete DOM actions per second consistently
    }

    if (data.keystrokes > 0 && data.session_duration_ms < 100) {
      score += 0.4; // Typing instantly after load
    }

    // Return safely capped score between 0 and 1
    return Math.min(Math.max(score, 0.0), 1.0);
  }
}
