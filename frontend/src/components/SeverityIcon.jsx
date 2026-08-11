import { CheckCircleIcon, InfoIcon, WarningDiamondIcon, WarningOctagonIcon } from "@phosphor-icons/react";

const ICON = {
  critical: WarningOctagonIcon,
  high: WarningDiamondIcon,
  medium: InfoIcon,
  low: CheckCircleIcon,
};

export default function SeverityIcon({ severity, size = 12 }) {
  const Icon = ICON[severity] || InfoIcon;
  return <Icon size={size} weight="fill" />;
}
