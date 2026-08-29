use std::collections::HashMap;
use std::sync::Arc;

use keyring_core::{api::CredentialStoreApi, Error as KeyringError};
use reqwest::{Client, Method, StatusCode, Url};
use serde_json::{json, Value};
use thiserror::Error;
use windows_native_keyring_store::Store;

const CORE_SERVICE: &str = "orbit-core.local-client-auth";
const CORE_ACCOUNT: &str = "loopback-core";
const CORE_BASE_URL: &str = "http://127.0.0.1:8765";

#[derive(Debug, Error)]
pub enum CoreClientError {
    #[error("OS credential store is unavailable.")]
    CredentialStore,
    #[error("Local Core credential is unavailable.")]
    CredentialMissing,
    #[error("Local Core rejected authentication.")]
    Unauthorized,
    #[error("Local Core is unavailable.")]
    Transport,
    #[error("Local Core returned an invalid response.")]
    InvalidResponse,
    #[error("Local Core route is invalid.")]
    InvalidRoute,
}

pub trait CredentialSource: Send + Sync {
    fn load(&self) -> Result<String, CoreClientError>;
}

pub struct OsCredentialStore;

impl CredentialSource for OsCredentialStore {
    fn load(&self) -> Result<String, CoreClientError> {
        let store = Store::new().map_err(|_| CoreClientError::CredentialStore)?;

        load_credential_from_targets(|target| {
            let modifiers = HashMap::from([("target", target)]);
            let entry = store
                .build(CORE_SERVICE, CORE_ACCOUNT, Some(&modifiers))
                .map_err(|_| CoreClientError::CredentialStore)?;
            match entry.get_password() {
                Ok(token) => Ok(Some(token)),
                Err(KeyringError::NoEntry) => Ok(None),
                Err(_) => Err(CoreClientError::CredentialStore),
            }
        })
    }
}

fn credential_targets() -> [String; 2] {
    [
        CORE_SERVICE.to_string(),
        format!("{CORE_ACCOUNT}@{CORE_SERVICE}"),
    ]
}

fn load_credential_from_targets<F>(mut load: F) -> Result<String, CoreClientError>
where
    F: FnMut(&str) -> Result<Option<String>, CoreClientError>,
{
    // Python WinVault stores the current value under the service target.
    // The account@service target is legacy rotation compatibility only.
    for target in credential_targets() {
        if let Some(token) = load(&target)? {
            if !token.is_empty() {
                return Ok(token);
            }
        }
    }

    Err(CoreClientError::CredentialMissing)
}

#[derive(Clone, Copy)]
enum CoreRoute {
    Status,
    Conversation,
    VoiceState,
}

impl CoreRoute {
    fn path(self) -> &'static str {
        match self {
            Self::Status => "/v1/status",
            Self::Conversation => "/v1/conversation",
            Self::VoiceState => "/v1/voice/state",
        }
    }
}

pub struct CoreClient {
    http: Client,
    credentials: Arc<dyn CredentialSource>,
    base_url: Url,
}

impl CoreClient {
    pub fn new() -> Result<Self, CoreClientError> {
        Self::with_source(Arc::new(OsCredentialStore))
    }

    pub fn with_source(credentials: Arc<dyn CredentialSource>) -> Result<Self, CoreClientError> {
        let base_url = Url::parse(CORE_BASE_URL).map_err(|_| CoreClientError::InvalidRoute)?;
        let http = Client::builder()
            .no_proxy()
            .build()
            .map_err(|_| CoreClientError::Transport)?;
        Ok(Self {
            http,
            credentials,
            base_url,
        })
    }

    pub async fn status(&self) -> Result<Value, CoreClientError> {
        let response = self
            .http
            .get(self.health_url()?)
            .send()
            .await
            .map_err(|_| CoreClientError::Transport)?;
        if response.status() != StatusCode::NO_CONTENT {
            return Err(CoreClientError::Transport);
        }
        self.request_json(CoreRoute::Status, Method::GET, None)
            .await
    }

    pub async fn conversation(&self, text: String) -> Result<Value, CoreClientError> {
        if text.trim().is_empty() {
            return Err(CoreClientError::InvalidResponse);
        }
        self.request_json(
            CoreRoute::Conversation,
            Method::POST,
            Some(json!({ "text": text })),
        )
        .await
    }

    pub async fn voice_state(&self, state: String) -> Result<Value, CoreClientError> {
        self.request_json(
            CoreRoute::VoiceState,
            Method::POST,
            Some(json!({ "state": state })),
        )
        .await
    }

    async fn request_json(
        &self,
        route: CoreRoute,
        method: Method,
        body: Option<Value>,
    ) -> Result<Value, CoreClientError> {
        let token = self.credentials.load()?;
        let response = self
            .send(route, method.clone(), body.clone(), &token)
            .await?;
        if response.status() == StatusCode::UNAUTHORIZED {
            let refreshed = self.credentials.load()?;
            let retry = self.send(route, method, body, &refreshed).await?;
            return self.decode(retry).await;
        }
        self.decode(response).await
    }

    async fn send(
        &self,
        route: CoreRoute,
        method: Method,
        body: Option<Value>,
        token: &str,
    ) -> Result<reqwest::Response, CoreClientError> {
        let mut request = self
            .http
            .request(method, self.route_url(route)?)
            .header(reqwest::header::AUTHORIZATION, format!("Bearer {token}"));
        if let Some(body) = body {
            request = request.json(&body);
        }
        request.send().await.map_err(|_| CoreClientError::Transport)
    }

    async fn decode(&self, response: reqwest::Response) -> Result<Value, CoreClientError> {
        if response.status() == StatusCode::UNAUTHORIZED {
            return Err(CoreClientError::Unauthorized);
        }
        if !response.status().is_success() {
            return Err(CoreClientError::Transport);
        }
        response
            .json::<Value>()
            .await
            .map_err(|_| CoreClientError::InvalidResponse)
    }

    fn health_url(&self) -> Result<Url, CoreClientError> {
        self.base_url
            .join("/healthz")
            .map_err(|_| CoreClientError::InvalidRoute)
    }

    fn route_url(&self, route: CoreRoute) -> Result<Url, CoreClientError> {
        let url = self
            .base_url
            .join(route.path())
            .map_err(|_| CoreClientError::InvalidRoute)?;
        if url.query().is_some() || url.fragment().is_some() {
            return Err(CoreClientError::InvalidRoute);
        }
        Ok(url)
    }
}

fn command_error(error: CoreClientError) -> String {
    error.to_string()
}

#[tauri::command]
pub async fn core_status(state: tauri::State<'_, CoreClient>) -> Result<Value, String> {
    state.status().await.map_err(command_error)
}

#[tauri::command]
pub async fn core_conversation(
    text: String,
    state: tauri::State<'_, CoreClient>,
) -> Result<Value, String> {
    state.conversation(text).await.map_err(command_error)
}

#[tauri::command]
pub async fn core_voice_state(
    voice_state: String,
    state: tauri::State<'_, CoreClient>,
) -> Result<Value, String> {
    state.voice_state(voice_state).await.map_err(command_error)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    struct MemoryCredentials(Mutex<Vec<String>>);

    impl CredentialSource for MemoryCredentials {
        fn load(&self) -> Result<String, CoreClientError> {
            self.0
                .lock()
                .map_err(|_| CoreClientError::CredentialStore)?
                .pop()
                .ok_or(CoreClientError::CredentialMissing)
        }
    }

    #[test]
    fn routes_are_fixed_and_have_no_query() {
        assert_eq!(CoreRoute::Status.path(), "/v1/status");
        assert!(CoreRoute::Conversation.path().starts_with("/v1/"));
        let client = CoreClient::with_source(Arc::new(MemoryCredentials(Mutex::new(vec![]))))
            .expect("client construction must not access keyring");
        assert_eq!(
            client.route_url(CoreRoute::Status).unwrap().as_str(),
            "http://127.0.0.1:8765/v1/status"
        );
    }

    #[test]
    fn public_errors_never_contain_credential_values() {
        let error = CoreClientError::Unauthorized.to_string();
        assert_eq!(error, "Local Core rejected authentication.");
        assert!(!error.contains("token"));
    }

    #[test]
    fn credential_targets_match_python_winvault_rotation_order() {
        assert_eq!(
            credential_targets(),
            [
                "orbit-core.local-client-auth".to_string(),
                "loopback-core@orbit-core.local-client-auth".to_string(),
            ]
        );
    }

    #[test]
    fn current_python_service_credential_wins_over_legacy_rotation_token() {
        let current = "current-token";
        let legacy = "legacy-rotation-token";
        let token = load_credential_from_targets(|target| {
            Ok(match target {
                "orbit-core.local-client-auth" => Some(current.to_string()),
                "loopback-core@orbit-core.local-client-auth" => Some(legacy.to_string()),
                _ => None,
            })
        })
        .unwrap();

        assert_eq!(token, current);
    }

    #[test]
    fn legacy_rotation_token_is_used_only_when_current_credential_is_missing() {
        let token = load_credential_from_targets(|target| {
            Ok(match target {
                "orbit-core.local-client-auth" => None,
                "loopback-core@orbit-core.local-client-auth" => Some("legacy-token".to_string()),
                _ => None,
            })
        })
        .unwrap();

        assert_eq!(token, "legacy-token");
    }

    #[test]
    fn missing_current_and_legacy_credentials_fail_closed() {
        let error = load_credential_from_targets(|_| Ok(None)).unwrap_err();

        assert!(matches!(error, CoreClientError::CredentialMissing));
        assert_eq!(error.to_string(), "Local Core credential is unavailable.");
    }

    #[test]
    fn credential_store_failure_never_falls_back_to_a_stale_token() {
        let mut legacy_was_read = false;
        let error = load_credential_from_targets(|target| {
            if target == "orbit-core.local-client-auth" {
                return Err(CoreClientError::CredentialStore);
            }
            legacy_was_read = true;
            Ok(Some("legacy-token".to_string()))
        })
        .unwrap_err();

        assert!(matches!(error, CoreClientError::CredentialStore));
        assert!(!legacy_was_read);
        assert!(!error.to_string().contains("legacy-token"));
    }
}
