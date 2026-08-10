import { CraneTower } from "@phosphor-icons/react";

export default function ComingSoonPage({ title }) {
  return (
    <div className="coming-soon">
      <CraneTower size={32} weight="duotone" />
      <h2>{title}</h2>
      <p className="muted">Màn hình này đang chờ thiết kế mới, sẽ nối API sau khi có UI.</p>
    </div>
  );
}
