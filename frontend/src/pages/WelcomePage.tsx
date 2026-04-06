import { useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Button from "@mui/material/Button";
import Stepper from "@mui/material/Stepper";
import Step from "@mui/material/Step";
import StepLabel from "@mui/material/StepLabel";
import { useNavigate } from "react-router-dom";
import { useUIStore } from "../store/uiStore";

const steps = ["Welcome", "Connect a Source", "Create a Channel", "Done"];

export default function WelcomePage() {
  const [activeStep, setActiveStep] = useState(0);
  const navigate = useNavigate();
  const { dismissWelcome } = useUIStore();

  const handleFinish = () => {
    dismissWelcome();
    navigate("/");
  };

  return (
    <Box sx={{ maxWidth: 600, mx: "auto", mt: 4 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>
        Welcome to EXStreamTV
      </Typography>
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>
      <Card>
        <CardContent>
          {activeStep === 0 && (
            <Typography>
              EXStreamTV turns your media library into a live TV experience. Set
              up channels, schedules, and distribute via M3U / XMLTV.
            </Typography>
          )}
          {activeStep === 1 && (
            <Typography>
              Connect a Plex or Jellyfin server under{" "}
              <strong>Sources</strong> to import your media.
            </Typography>
          )}
          {activeStep === 2 && (
            <Typography>
              Create channels under <strong>Channels</strong> and assign a
              schedule to start streaming.
            </Typography>
          )}
          {activeStep === 3 && (
            <Typography>
              You're all set! Access your playlist at{" "}
              <code>/iptv/playlist.m3u</code>.
            </Typography>
          )}
        </CardContent>
      </Card>
      <Box sx={{ display: "flex", justifyContent: "space-between", mt: 3 }}>
        <Button
          disabled={activeStep === 0}
          onClick={() => setActiveStep((s) => s - 1)}
        >
          Back
        </Button>
        {activeStep < steps.length - 1 ? (
          <Button variant="contained" onClick={() => setActiveStep((s) => s + 1)}>
            Next
          </Button>
        ) : (
          <Button variant="contained" onClick={handleFinish}>
            Get Started
          </Button>
        )}
      </Box>
    </Box>
  );
}
