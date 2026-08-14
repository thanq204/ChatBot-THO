import Card from "../components/Card.jsx";
import CommandContentEditor from "../components/CommandContentEditor.jsx";

export default function BotCommandsPage() {
  return (
    <div className="page-grid">
      <div className="page-grid__row">
        <Card title="Nội dung lệnh bot" className="span-12">
          <CommandContentEditor />
        </Card>
      </div>
    </div>
  );
}
