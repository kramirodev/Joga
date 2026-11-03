package expo.modules.passkeyproof

import android.os.Build
import android.util.Base64
import androidx.credentials.CreatePublicKeyCredentialRequest
import androidx.credentials.CreatePublicKeyCredentialResponse
import androidx.credentials.CredentialManager
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetPublicKeyCredentialOption
import androidx.credentials.PublicKeyCredential
import androidx.credentials.exceptions.CreateCredentialCancellationException
import androidx.credentials.exceptions.CreateCredentialException
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import androidx.credentials.exceptions.publickeycredential.CreatePublicKeyCredentialDomException
import androidx.credentials.exceptions.publickeycredential.GetPublicKeyCredentialDomException
import expo.modules.kotlin.functions.Coroutine
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.security.MessageDigest
import java.security.SecureRandom
import org.json.JSONArray
import org.json.JSONObject

/**
 * Prova mínima de passkey no Android via Credential Manager.
 *
 * O RP ID precisa estar associado ao package/certificado em
 * `https://<rpId>/.well-known/assetlinks.json`. Aqui não há backend: o desafio é
 * gerado localmente e a resposta é devolvida ao JavaScript apenas para exibição.
 */
class PasskeyProofModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("PasskeyProof")

    Function("getPlatformSummary") {
      "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"
    }

    AsyncFunction("createPasskeyAsync") Coroutine { rpId: String, rpName: String, userName: String ->
      val activity = appContext.currentActivity
        ?: throw IllegalStateException("Nenhuma Activity ativa para abrir o Credential Manager.")

      val credentialManager = CredentialManager.create(activity)
      val challenge = randomChallenge()

      val requestJson = JSONObject().apply {
        put("challenge", challenge)
        put(
          "rp",
          JSONObject().apply {
            put("name", rpName)
            put("id", rpId)
          },
        )
        put(
          "user",
          JSONObject().apply {
            put("id", challenge)
            put("name", userName)
            put("displayName", userName)
          },
        )
        put(
          "pubKeyCredParams",
          JSONArray().apply {
            put(
              JSONObject().apply {
                put("type", "public-key")
                put("alg", -7)
              },
            )
            put(
              JSONObject().apply {
                put("type", "public-key")
                put("alg", -257)
              },
            )
          },
        )
        put(
          "authenticatorSelection",
          JSONObject().apply {
            put("residentKey", "required")
            put("userVerification", "required")
          },
        )
        put("timeout", 300000)
        put("attestation", "none")
      }.toString()

      val response =
        try {
          credentialManager.createCredential(
            activity,
            CreatePublicKeyCredentialRequest(requestJson),
          ) as CreatePublicKeyCredentialResponse
        } catch (error: CreateCredentialCancellationException) {
          throw IllegalStateException("Criação de passkey cancelada pelo usuário.")
        } catch (error: CreateCredentialException) {
          throw IllegalStateException(describeCredentialError("Criação de passkey", error))
        }

      registrationResult(response)
    }

    AsyncFunction("createPasskeyFromRequestAsync") Coroutine { requestJson: String ->
      val activity = appContext.currentActivity
        ?: throw IllegalStateException("Nenhuma Activity ativa para abrir o Credential Manager.")

      val credentialManager = CredentialManager.create(activity)
      val response =
        try {
          credentialManager.createCredential(
            activity,
            CreatePublicKeyCredentialRequest(requestJson),
          ) as CreatePublicKeyCredentialResponse
        } catch (error: CreateCredentialCancellationException) {
          throw IllegalStateException("Criação de passkey cancelada pelo usuário.")
        } catch (error: CreateCredentialException) {
          throw IllegalStateException(describeCredentialError("Criação de passkey", error))
        }

      registrationResult(response)
    }

    AsyncFunction("getPasskeyAsync") Coroutine { rpId: String, credentialId: String ->
      val activity = appContext.currentActivity
        ?: throw IllegalStateException("Nenhuma Activity ativa para abrir o Credential Manager.")

      val credentialManager = CredentialManager.create(activity)

      val requestJson = JSONObject().apply {
        put("challenge", randomChallenge())
        put("rpId", rpId)
        put(
          "allowCredentials",
          JSONArray().apply {
            if (credentialId.isNotBlank()) {
              put(
                JSONObject().apply {
                  put("type", "public-key")
                  put("id", credentialId)
                },
              )
            }
          },
        )
        put("userVerification", "required")
        put("timeout", 300000)
      }.toString()

      val response =
        try {
          credentialManager.getCredential(
            activity,
            GetCredentialRequest(listOf(GetPublicKeyCredentialOption(requestJson))),
          )
        } catch (error: GetCredentialCancellationException) {
          throw IllegalStateException("Autenticação com passkey cancelada pelo usuário.")
        } catch (error: NoCredentialException) {
          throw IllegalStateException("Nenhuma passkey disponível para este RP ID neste aparelho.")
        } catch (error: GetCredentialException) {
          throw IllegalStateException(
            describeCredentialError("Autenticação com passkey", error),
          )
        }

      val credential = response.credential
      if (credential !is PublicKeyCredential) {
        throw IllegalStateException("O Credential Manager não retornou uma credencial de chave pública.")
      }

      authenticationResult(credential, rpId)
    }

    AsyncFunction("getPasskeyFromRequestAsync") Coroutine { requestJson: String ->
      val activity = appContext.currentActivity
        ?: throw IllegalStateException("Nenhuma Activity ativa para abrir o Credential Manager.")

      val credentialManager = CredentialManager.create(activity)
      val response =
        try {
          credentialManager.getCredential(
            activity,
            GetCredentialRequest(listOf(GetPublicKeyCredentialOption(requestJson))),
          )
        } catch (error: GetCredentialCancellationException) {
          throw IllegalStateException("Autenticação com passkey cancelada pelo usuário.")
        } catch (error: NoCredentialException) {
          throw IllegalStateException("Nenhuma passkey disponível para este RP ID neste aparelho.")
        } catch (error: GetCredentialException) {
          throw IllegalStateException(
            describeCredentialError("Autenticação com passkey", error),
          )
        }

      val credential = response.credential
      if (credential !is PublicKeyCredential) {
        throw IllegalStateException("O Credential Manager não retornou uma credencial de chave pública.")
      }

      authenticationResult(credential, JSONObject(requestJson).optString("rpId"))
    }
  }

  private fun registrationResult(response: CreatePublicKeyCredentialResponse): Map<String, Any?> {
    val registration = JSONObject(response.registrationResponseJson)
    val clientData = decodeClientData(registration.optJSONObject("response")?.optString("clientDataJSON"))

    return mapOf(
      "credentialId" to registration.optString("id"),
      "rawId" to registration.optString("rawId"),
      "clientDataType" to clientData.optString("type"),
      "clientDataOrigin" to clientData.optString("origin"),
      "clientDataChallenge" to clientData.optString("challenge"),
      "registrationResponseJson" to response.registrationResponseJson,
    )
  }

  private fun authenticationResult(
    credential: PublicKeyCredential,
    rpId: String,
  ): Map<String, Any?> {
    val assertion = JSONObject(credential.authenticationResponseJson)
    val clientData = decodeClientData(assertion.optJSONObject("response")?.optString("clientDataJSON"))
    val authenticatorData =
      decodeBase64Url(assertion.optJSONObject("response")?.optString("authenticatorData").orEmpty())

    val expectedRpIdHash = MessageDigest.getInstance("SHA-256").digest(rpId.toByteArray(Charsets.UTF_8))
    val rpIdHashMatches =
      authenticatorData.size >= 32 &&
        authenticatorData.copyOfRange(0, 32).contentEquals(expectedRpIdHash)

    val flags = if (authenticatorData.size > 32) authenticatorData[32].toInt() and 0xFF else 0

    return mapOf(
      "credentialId" to assertion.optString("id"),
      "rawId" to assertion.optString("rawId"),
      "clientDataType" to clientData.optString("type"),
      "clientDataOrigin" to clientData.optString("origin"),
      "rpIdHashMatches" to rpIdHashMatches,
      "userPresent" to (flags and 0x01 != 0),
      "userVerified" to (flags and 0x04 != 0),
      "authenticationResponseJson" to credential.authenticationResponseJson,
    )
  }

  private fun describeCredentialError(prefix: String, error: Exception): String {
    val type =
      when (error) {
        is CreatePublicKeyCredentialDomException -> error.domError.type
        is GetPublicKeyCredentialDomException -> error.domError.type
        else -> null
      }
    val message = error.message?.trim().orEmpty().ifBlank { null }
    return listOfNotNull(prefix, type, message).joinToString(" • ")
  }

  private fun randomChallenge(): String {
    val bytes = ByteArray(32)
    SecureRandom().nextBytes(bytes)
    return encodeBase64Url(bytes)
  }

  private fun encodeBase64Url(bytes: ByteArray): String =
    Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)

  private fun decodeBase64Url(value: String): ByteArray {
    if (value.isBlank()) {
      return ByteArray(0)
    }
    return Base64.decode(value, Base64.URL_SAFE or Base64.NO_WRAP)
  }

  private fun decodeClientData(value: String?): JSONObject {
    if (value.isNullOrBlank()) {
      return JSONObject()
    }
    return JSONObject(String(decodeBase64Url(value), Charsets.UTF_8))
  }
}
