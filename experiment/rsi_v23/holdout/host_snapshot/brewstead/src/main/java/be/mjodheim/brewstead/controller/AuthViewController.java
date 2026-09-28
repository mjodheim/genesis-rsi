package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.account.RegisterForm;
import be.mjodheim.brewstead.service.RegistrationService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;

@Controller
@RequiredArgsConstructor
public class AuthViewController {

    private final RegistrationService registrationService;

    @GetMapping("/login")
    public String login() {
        return "auth/login";
    }

    @GetMapping("/register")
    public String registerForm(Model model) {
        model.addAttribute("form", new RegisterForm());
        return "auth/register";
    }

    @PostMapping("/register")
    public String register(@Valid @ModelAttribute("form") RegisterForm form,
                           BindingResult binding,
                           Model model) {
        if (binding.hasErrors()) {
            model.addAttribute("error", binding.getAllErrors().getFirst().getDefaultMessage());
            return "auth/register";
        }

        try {
            registrationService.register(form);
        } catch (IllegalArgumentException | IllegalStateException refused) {
            model.addAttribute("error", refused.getMessage());
            return "auth/register";
        }

        return "redirect:/login?registered";
    }
}
