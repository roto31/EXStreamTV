import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Divider from "@mui/material/Divider";
import { usePersona } from "../../context/PersonaContext";

export default function GeneralSettingsPage() {
  const { personaId } = usePersona();
  return (
    <Box>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Settings — General
      </Typography>
      <Card>
        <CardContent>
          <List disablePadding>
            <ListItem>
              <ListItemText
                primary="Active persona"
                secondary={personaId}
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemText
                primary="Persona storage"
                secondary="sessionStorage key: exstreamtv.persona_id"
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemText
                primary="API base"
                secondary="Vite proxies /api and /iptv → 127.0.0.1:8411 in dev. Set VITE_API_BASE for split deploys."
              />
            </ListItem>
          </List>
        </CardContent>
      </Card>
    </Box>
  );
}
