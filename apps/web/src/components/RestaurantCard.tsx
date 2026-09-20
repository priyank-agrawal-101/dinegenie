import type { Money, Recommendation } from "../api/types";

export function formatCost(cost: Money): string {
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: cost.currency, maximumFractionDigits: 2 }).format(cost.amount);
  } catch { return `${cost.currency} ${cost.amount.toLocaleString("en-IN")}`; }
}

export function RestaurantCard({ restaurant, rank }: { restaurant: Recommendation; rank: number }) {
  const cost = restaurant.estimated_cost;
  const basis = cost?.basis === "for_two" ? "Cost for two:" :
    cost?.basis === "per_person" ? "Cost per person:" : "Estimated cost · basis unavailable";
  return <li className="restaurant-card"><article aria-labelledby={`restaurant-${restaurant.restaurant_id}`}>
    <span className="rank">{rank}</span>
    <div className="restaurant-content">
      <div className="restaurant-topline"><div><h3 id={`restaurant-${restaurant.restaurant_id}`}>{restaurant.name}</h3><p className="restaurant-locality">{restaurant.location}{restaurant.city ? `, ${restaurant.city}` : ""}</p></div>
        <span className="rating">{restaurant.rating === null ? "Rating unavailable" : <><span aria-hidden="true">★</span>{restaurant.rating.toFixed(1)}</>}</span></div>
      <p className="restaurant-cuisines">{restaurant.cuisines.length ? restaurant.cuisines.join(" · ") : "Cuisine unavailable"}</p>
      <div className="cost-row">{cost ? <><span>{basis}</span><strong>{formatCost(cost)}</strong></> : <strong>Estimated cost unavailable</strong>}</div>
      {restaurant.explanation && <div className="explanation"><span className="fit-check" aria-hidden="true">✓</span><div><h4>Why it fits</h4><p>{restaurant.explanation}</p></div></div>}
      {restaurant.matched_preferences.length > 0 && <div className="evidence"><h4>Matched preferences</h4><ul className="tag-list">{restaurant.matched_preferences.map((value, index) => <li key={`${value}-${index}`}>{value}</li>)}</ul></div>}
      {restaurant.unverified_preferences.length > 0 && <div className="unverified"><h4>Not verified by the dataset</h4><p>{restaurant.unverified_preferences.join(" · ")}</p></div>}
    </div>
  </article></li>;
}
