import { Card, Typography } from "antd";

export function Panel({ title, description, actions, children }) {
  return <Card className="min-w-0" size="small" title={title && <h2>{title}</h2>} extra={actions}>
    {description && <div className="mb-2"><Typography.Text type="secondary">{description}</Typography.Text></div>}
    {children}
  </Card>;
}
