export const stamp = (seconds, short = false) =>
  new Date(seconds * 1000).toISOString().slice(11, short ? 16 : 19);
export const levelName = {
  verified: "Verified",
  developing: "Developing",
  rumor: "Unverified rumor",
  dismissed: "Dismissed",
};
export const numeric = (value) => new Intl.NumberFormat("en-US").format(value);
export const marketMove = (prices) => (prices.at(-1) / prices[0] - 1) * 100;
export const percent = (number) =>
  `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
