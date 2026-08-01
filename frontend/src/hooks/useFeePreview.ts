import { useMemo } from "react";

import { brokerNote, calculateLotFees, formatMyr } from "@/lib/fee-calculator";
import type { BrokerConfigResponse } from "@/lib/types";

/** Shared live fee-preview computation (FE-2.1's AddPositionDialog, FE-2.2's
 * AddLotDialog) — display-only, decimal.js-backed (see lib/fee-calculator.ts).
 */
export function useFeePreview(broker: BrokerConfigResponse | undefined, shares: string, price: string) {
  return useMemo(() => {
    const sharesNum = parseInt(shares, 10);
    if (!broker || !sharesNum || sharesNum <= 0 || !price || parseFloat(price) <= 0) {
      return null;
    }
    try {
      const fees = calculateLotFees(sharesNum, price, broker);
      return {
        initialAmount: formatMyr(fees.initialAmount),
        brokerageFee: formatMyr(fees.brokerageFee),
        clearingFee: formatMyr(fees.clearingFee),
        stampDuty: formatMyr(fees.stampDuty),
        allInCost: formatMyr(fees.allInCost),
        note: brokerNote(broker, fees.initialAmount),
      };
    } catch {
      return null;
    }
  }, [broker, shares, price]);
}
