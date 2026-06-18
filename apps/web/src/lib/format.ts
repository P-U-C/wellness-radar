export function formatAgeFromHours(ageHours?: number | null): string {
  if (ageHours === null || ageHours === undefined || Number.isNaN(ageHours)) {
    return "n/a";
  }
  if (ageHours < 1) {
    return "<1h";
  }
  if (ageHours < 48) {
    return `${Math.round(ageHours)}h`;
  }
  return `${Math.round(ageHours / 24)}d`;
}

export function formatVerified(ageHours?: number | null): string {
  const age = formatAgeFromHours(ageHours);
  return age === "n/a" ? "freshness n/a" : `verified ${age} ago`;
}

export function formatAgeFromIso(value: string): string {
  const time = Date.parse(value);
  if (Number.isNaN(time)) {
    return "n/a";
  }
  const hours = Math.max(0, (Date.now() - time) / 3_600_000);
  return formatAgeFromHours(hours);
}

export function formatScore(value: number): string {
  return value.toFixed(2);
}

export function sentenceCase(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
